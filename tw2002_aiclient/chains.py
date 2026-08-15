"""Longest-profit-chain finder -- pure cycle search (no world-model).

Decoupled from `trade_adapter.py`: callers pass `TradeHop` edges (synthetic
or adapted from a world-model). Every hop in a returned chain has
margin > 0. Rank: hop-count desc, then cr/turn desc.

See `canon/strategy/trade-loops.md` -- the chain finder is "a world-model
consumer that surfaces to the operator ... a suggestion and a cockpit
centerpiece ... not an executor. It reads persisted port records via
`trade_adapter.build_trade_hops` ... it sends nothing and drives nothing."
Nothing in this module imports session/protocol/adapter code, and nothing
here decides which chain to run -- that is the priority layer's job.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence


@dataclass(frozen=True)
class TradeHop:
    frm: int
    to: int
    commodity: str
    margin: float
    turns: int = 1


@dataclass(frozen=True)
class ProfitChain:
    sectors: tuple[int, ...]  # closed cycle, first == last
    hops: tuple[TradeHop, ...]
    overall_profit: float
    turns: int
    cr_per_turn: float
    cr_per_execution: float


# Chain execute-floor thresholds -- ranking/gating INPUTS only, per
# `canon/strategy/trade-loops.md` §"Chain execute-floor thresholds --
# rule-guard inputs". These decide what the priority layer offers and how
# it orders candidates; they never authorize driving over an unrecognized
# screen -- the stop-on-unknown invariant is prior to and independent of
# any threshold here (canon, same section).
MIN_CHAIN_LINKS_TO_EXECUTE = 2
MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE = 4


def is_executable_chain(chain: ProfitChain) -> bool:
    """Whether `chain` clears the discovery-only floor (canon: "a chain
    shorter than two links ... is discovery-only: it is never offered as
    an executable earn macro"). The ONE pure consumer of
    `MIN_CHAIN_LINKS_TO_EXECUTE` -- no picker, no EV scorer, no "which
    loop should we run" logic lives here; that belongs to the priority
    layer this module does not import."""
    return len(chain.hops) >= MIN_CHAIN_LINKS_TO_EXECUTE


def _normalize_cycle(sectors: tuple[int, ...]) -> tuple[int, ...]:
    """Rotate so the smallest sector id is first (keep closed)."""
    if len(sectors) < 2 or sectors[0] != sectors[-1]:
        return sectors
    body = list(sectors[:-1])
    if not body:
        return sectors
    i = body.index(min(body))
    rotated = body[i:] + body[:i]
    return tuple(rotated + [rotated[0]])


DEFAULT_MAX_SEARCH_STEPS = 100_000
"""Global cap on DFS frame-visits across the *whole* `find_profit_chains_with_note`
search (summed over every start sector, not per-start). Protects both
wall-clock time and the Python call stack on pathological graphs --
`trade_adapter.DEFAULT_MAX_HOPS` bounds the ADAPTER's edge output, not
the finder's search cost, and a few thousand mutually-compatible edges
(see that constant's live-witness rationale) is already a dense graph
(see WO-CHAIN-SEARCH-BUDGET: an
unbranched ring of ~999 sectors overflowed Python's recursion limit
before this budget existed; a complete K9 took 6.43s for one chain).
This is a safety rail, not an EV-optimizer -- canon's hop-count-desc/
cr-per-turn-desc ranking (`rank_chains`) is unaffected by truncation;
whatever chains were found before the budget fired are ranked exactly
as they always were."""


def find_profit_chains_with_note(
    hops: Sequence[TradeHop],
    *,
    min_hops: int = 2,
    max_hops: Optional[int] = None,
    max_search_steps: int = DEFAULT_MAX_SEARCH_STEPS,
) -> tuple[list[ProfitChain], Optional[str]]:
    """Every closed profit cycle discoverable in `hops`, ranked by
    `rank_chains`, plus an optional truncation note. Iterative DFS
    (explicit stack -- see `_search_cycles`) so `RecursionError` cannot
    escape regardless of graph size; search is bounded by
    `max_search_steps` (see `DEFAULT_MAX_SEARCH_STEPS`). `note` is `None`
    unless `max_search_steps` was exhausted, in which case it names the
    budget, how many chains were found before truncation, and how many
    start sectors were fully searched -- a truncated result must never
    look identical to a complete one."""
    return _search_cycles(
        hops, min_hops=min_hops, max_hops=max_hops, max_search_steps=max_search_steps
    )


def _search_cycles(
    hops: Sequence[TradeHop],
    *,
    min_hops: int,
    max_hops: Optional[int],
    max_search_steps: int,
) -> tuple[list[ProfitChain], Optional[str]]:
    """Internal search routine behind `find_profit_chains_with_note`.
    Iterative DFS with an explicit stack of resumable
    hop-iterators -- never Python recursion, so `RecursionError` is
    structurally unreachable at any graph size (a depth constant alone
    would only postpone the crash) -- that reproduces the exact
    traversal order of the pre-budget recursive algorithm: each stack
    frame processes its node's outgoing hops in listed order, a hop that
    closes the cycle back to `start` records immediately (matching the
    original's `continue`, staying in the same frame), and a hop that
    descends fully explores that subtree via later stack frames before
    this frame resumes its own remaining hops (matching a `dfs()` call
    returning before the loop continues). `max_search_steps` bounds
    total frame-visits across every start sector combined -- it is a
    node/frame counter, not a depth cap, because the K-graph blowup this
    guards against is breadth (branching), not depth."""
    usable = [h for h in hops if h.margin > 0 and h.turns > 0]
    adj: dict[int, list[TradeHop]] = defaultdict(list)
    in_degree: dict[int, int] = defaultdict(int)
    for h in usable:
        adj[h.frm].append(h)
        in_degree[h.to] += 1

    found: dict[tuple[int, ...], ProfitChain] = {}

    def record(path_nodes: list[int], path_hops: list[TradeHop]) -> None:
        sectors = _normalize_cycle(tuple(path_nodes + [path_nodes[0]]))
        # Rotate hops to match normalized sector start.
        start_sector = sectors[0]
        rot = path_nodes.index(start_sector)
        hops_rot = tuple(path_hops[rot:] + path_hops[:rot])
        overall = sum(h.margin for h in hops_rot)
        turns = sum(h.turns for h in hops_rot)
        chain = ProfitChain(
            sectors=sectors,
            hops=hops_rot,
            overall_profit=overall,
            turns=turns,
            cr_per_turn=(overall / turns) if turns else 0.0,
            cr_per_execution=overall,
        )
        key = sectors
        prev = found.get(key)
        if prev is None or chain.cr_per_turn > prev.cr_per_turn:
            found[key] = chain

    def frame_hops(node: int, depth: int) -> Sequence[TradeHop]:
        # Mirrors the original recursive `dfs`'s top-of-function guard
        # (`if len(path_hops) >= max_hops: return`): a frame entered
        # already AT the cap examines zero hops -- not even a closing
        # one -- exactly like the original returning before its loop.
        if max_hops is not None and depth >= max_hops:
            return ()
        return adj.get(node, ())

    # Skip in-degree-0 starts: a cycle that begins at S must hop back to S,
    # so a node nothing trades into can never close (live academy: SSS
    # all-selling ports with out>0/in=0 burned the entire DFS budget as the
    # first starts while mutual pairs existed elsewhere — bubbles fell back
    # to a 2-port class pair). Prefer low out-degree next so tight pairs
    # surface before wide open trees.
    starts = sorted(
        (s for s in adj if in_degree[s] > 0),
        key=lambda s: (len(adj[s]), -in_degree[s], s),
    )
    steps = 0
    truncated = False
    completed_starts = 0
    for start in starts:
        if truncated:
            break
        path_nodes = [start]
        path_hops: list[TradeHop] = []
        in_path = {start}
        stack = [iter(frame_hops(start, 0))]
        while stack:
            steps += 1
            if steps > max_search_steps:
                truncated = True
                break
            advanced = False
            for hop in stack[-1]:
                nxt = hop.to
                if nxt == start and len(path_hops) + 1 >= min_hops:
                    record(path_nodes, path_hops + [hop])
                    continue
                if nxt in in_path:
                    continue
                if max_hops is not None and len(path_hops) + 1 > max_hops:
                    continue
                path_nodes.append(nxt)
                path_hops.append(hop)
                in_path.add(nxt)
                stack.append(iter(frame_hops(nxt, len(path_hops))))
                advanced = True
                break
            if not advanced:
                stack.pop()
                if len(path_nodes) > 1:
                    popped = path_nodes.pop()
                    in_path.discard(popped)
                    path_hops.pop()
        if not truncated:
            completed_starts += 1

    note = None
    if truncated:
        note = (
            f"chains: search budget exhausted at {max_search_steps} DFS steps "
            f"({len(found)} chain(s) found, {completed_starts}/{len(starts)} start "
            f"sector(s) fully searched before truncation) -- result is partial"
        )
    return rank_chains(list(found.values())), note



def hold_scaled_cr_per_turn(cr_per_turn: object, hold_count: object) -> Optional[float]:
    """Trip-rate EV: unit ``cr_per_turn`` × live hold count.

    Finder ``ProfitChain.cr_per_turn`` is *per-hold unit margin* (sum of hop
    margins / turns). Display / earn glances that need trip P&L scale by
    ship holds. Fail-closed: non-finite cr, non-positive int holds → None.
    Never invents a hold count. Ranking stays on the unit field (#527).
    """
    if isinstance(cr_per_turn, bool) or not isinstance(cr_per_turn, (int, float)):
        return None
    cr = float(cr_per_turn)
    if not math.isfinite(cr):
        return None
    if isinstance(hold_count, bool) or not isinstance(hold_count, int):
        return None
    if hold_count <= 0:
        return None
    return cr * float(hold_count)


def hold_count_from_status(status: object) -> Optional[int]:
    """Positive live hold count from a status mapping, or None.

    Prefers ``upgrade_player.current_holds``, then ``current_ship.total_holds``.
    Product callers: ``chain_status.ChainScalars`` depletion (via
    ``_hold_count_from_status``) and ``screens.py`` chain-panel hold scaling.
    """
    if not isinstance(status, Mapping):
        return None
    player = status.get("upgrade_player")
    if isinstance(player, Mapping):
        holds = player.get("current_holds")
        if isinstance(holds, int) and not isinstance(holds, bool) and holds > 0:
            return holds
    ship = status.get("current_ship")
    if isinstance(ship, Mapping):
        holds = ship.get("total_holds")
        if isinstance(holds, int) and not isinstance(holds, bool) and holds > 0:
            return holds
    return None



def rank_chains(chains: Sequence[ProfitChain]) -> list[ProfitChain]:
    """Canon discovery / priority-layer order: hop-count desc, then cr/turn.

    See `canon/strategy/trade-loops.md` § Ranking. Earn / credit-doubling
    surfaces that want yield-first use `rank_chains_by_yield` instead —
    do not flip this default.
    """
    return sorted(
        chains,
        key=lambda c: (len(c.hops), c.cr_per_turn),
        reverse=True,
    )


def rank_chains_by_yield(chains: Sequence[ProfitChain]) -> list[ProfitChain]:
    """Earn-surface order: credits-per-turn desc, then hop-count desc.

    Keeps a short high-yield pair (e.g. 2-hop @ 3.5) above a long thin
    cycle (e.g. 9-hop @ 1.0). Discovery/explore keeps `rank_chains`.
    """
    return sorted(
        chains,
        key=lambda c: (c.cr_per_turn, len(c.hops)),
        reverse=True,
    )


def rank_chains_by_longevity(
    chains: Sequence[ProfitChain],
    remaining_by_key: Mapping,
    *,
    base_rank: str = "discovery",
) -> list[ProfitChain]:
    """Down-rank chains whose predicted ``remaining_trades`` is low.

    Thin wrapper over :func:`chain_depletion.rank_chains_by_longevity` so
    discovery callers can import from ``chains`` without a second module.
    Unknown remaining never counts as depleted.
    """
    from tw2002_aiclient.chain_depletion import rank_chains_by_longevity as _rank

    return _rank(chains, remaining_by_key, base_rank=base_rank)
