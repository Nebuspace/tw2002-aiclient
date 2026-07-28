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

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Sequence


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
CHAIN_LINKS_PREFER_SEARCH_BELOW = MIN_CHAIN_LINKS_TO_EXECUTE
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


def find_profit_chains(
    hops: Sequence[TradeHop],
    *,
    min_hops: int = 2,
    max_hops: Optional[int] = None,
) -> list[ProfitChain]:
    usable = [h for h in hops if h.margin > 0 and h.turns > 0]
    adj: dict[int, list[TradeHop]] = defaultdict(list)
    for h in usable:
        adj[h.frm].append(h)

    found: dict[tuple[int, ...], ProfitChain] = {}

    def record(path_nodes: list[int], path_hops: list[TradeHop]) -> None:
        sectors = _normalize_cycle(tuple(path_nodes + [path_nodes[0]]))
        # Rotate hops to match normalized sector start.
        start = sectors[0]
        rot = path_nodes.index(start)
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

    def dfs(start: int, node: int, path_nodes: list[int], path_hops: list[TradeHop]) -> None:
        if max_hops is not None and len(path_hops) >= max_hops:
            return
        for hop in adj.get(node, ()):
            nxt = hop.to
            if nxt == start and len(path_hops) + 1 >= min_hops:
                record(path_nodes, path_hops + [hop])
                continue
            if nxt in path_nodes:
                continue
            if max_hops is not None and len(path_hops) + 1 > max_hops:
                continue
            dfs(start, nxt, path_nodes + [nxt], path_hops + [hop])

    for start in list(adj.keys()):
        dfs(start, start, [start], [])

    return rank_chains(list(found.values()))


def rank_chains(chains: Sequence[ProfitChain]) -> list[ProfitChain]:
    return sorted(
        chains,
        key=lambda c: (len(c.hops), c.cr_per_turn),
        reverse=True,
    )


def longest_profit_chain(
    hops: Sequence[TradeHop],
    **kwargs,
) -> Optional[ProfitChain]:
    chains = find_profit_chains(hops, **kwargs)
    return chains[0] if chains else None
