"""chain_detect -- class-derived PAIR LOOP recompute (WO-CHAIN-DETECT-WIRE).

The wired entry point: given a `world_id`, recompute the best known
class-derived pair loops and hand back a typed result the TUI (or CLI) can
read. Pure world-model read -- ZERO sends, ZERO execution, no curses, no
protocol import. Unlike `tw2002_aiclient/adapters.py`, which documents
itself as the entry into the *session engine* (every verb there is a
daemon round trip taking `run_dir`), this module never touches a session
at all: it is a read-only consumer of `trade_adapter.build_candidate_pairs`
(itself a pure `world_model` reader -- see that module's own docstring).

Scope, deliberately narrow (see WO-CHAIN-DETECT-WIRE dispatch, "settled
scope only"): a PAIR loop only -- no cycle search, no multi-hop chain, no
budget. `chains.py` is not imported here and is not touched by this WO at
all. A pair loop is the smallest chain canon defines
(`canon/strategy/trade-loops.md` §"Pair loop"): two ports, each buying
what the other sells, connected by a known route both ways.

Ranking (canon `trade-loops.md` §H1: "an adjacent pair is the cheapest
shape"): hop-count is degenerate here -- every candidate is exactly 2
hops -- so pairs rank by round-trip `turns` ascending (genuinely known
from the warp graph, never fabricated), then `(sector_a, sector_b)`
ascending for a total order so output is deterministic even across ties.
`trade_adapter.CandidatePair` already guarantees `sector_a < sector_b`,
so `(sector_a, sector_b)` IS `(min sector, max sector)`.

Honest empty (never a bare boolean): `PairLoopResult.reason` is one of
the `REASON_*` constants below, or `None` when `pairs` is non-empty --
mirrors the `ok`/`reason`/`detail` shape `adapters.py`'s `EnsureResult` /
`ExploreResult` / `AutoLoopResult` already use for a typed machine-
readable failure mode, rather than inventing a new vocabulary.

This module deliberately stops at the typed payload -- it does NOT render.
An earlier draft bridged straight into `loops/list_view.format_loop_row`
(a `CandidatePair`-shaped row squeezed through a taught-MACRO listing
column set), which put a hop count in a column that means recorded/mined
KEYSTROKE steps and silently dropped `turns`, the one genuinely-known
number on the row. Hub ruling (2026-07-28): `format_loop_row` is the WRONG
CONSUMER, not a thing to repair -- a `CandidatePair` is not a macro (no
`steps[]`, no `start_anchor`, claims neither `recorded` nor `mined`). The
dedicated pure formatter now lives in `chain_detect_view.py`
(`format_candidate_pair_lines`) -- see that module's own docstring for the
render-side rules (never `cockpit/chains.py`, never the taught `L)chains`
arm list).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Callable, Optional

from tw2002_aiclient import trade_adapter

# Typed empty-reason vocabulary -- checked in this fixed precedence order
# by `recompute` below, each naming a genuinely different situation so an
# operator (or a future coach surface) never has to guess which one fired:
REASON_NO_WORLD_MODEL = "no_world_model"  # this world has never recorded a single sector
REASON_FEWER_THAN_TWO_PORTS = "fewer_than_two_ports"  # <2 sectors carry a usable class triple, any age
REASON_ALL_STALE = "all_stale"  # >=2 valid triples exist, but <2 are within the class staleness ceiling
REASON_NO_COMPATIBLE_PAIRS = "no_compatible_pairs"  # >=2 fresh ports, none posture-complementary
REASON_COMPATIBLE_BUT_UNROUTED = "compatible_but_unrouted"  # a compatible pair exists, no known route both ways


@dataclass(frozen=True)
class PairLoopResult:
    """The one frozen result `recompute` returns. `pairs` is ranked
    (round-trip turns ascending, then sector-pair ascending) and is
    non-empty exactly when `reason` is `None`."""

    world_id: str
    pairs: tuple[trade_adapter.CandidatePair, ...]
    reason: Optional[str] = None
    detail: Optional[str] = None


def recompute(
    world_id: str,
    *,
    state_dir=None,
    config: Optional[trade_adapter.PairLoopConfig] = None,
    now: Optional[Callable[[], datetime.datetime]] = None,
) -> PairLoopResult:
    """Recompute pair loops for `world_id` from its current world-model
    state. Idempotent: given the same on-disk state and the same
    injected `now`, two calls return identical results -- there is no
    wall-clock read here beyond what the caller supplies, and every
    intermediate collection this function or `build_candidate_pairs`
    builds is sorted before it can affect output order."""
    pairs, stats = trade_adapter.build_candidate_pairs(
        world_id, state_dir=state_dir, config=config, now=now
    )

    if pairs:
        ranked = tuple(sorted(pairs, key=lambda p: (p.turns, p.sector_a, p.sector_b)))
        return PairLoopResult(world_id=world_id, pairs=ranked, reason=None, detail=None)

    if stats.known_sectors == 0:
        return PairLoopResult(world_id=world_id, pairs=(), reason=REASON_NO_WORLD_MODEL)
    if stats.class_valid_ports < 2:
        return PairLoopResult(world_id=world_id, pairs=(), reason=REASON_FEWER_THAN_TWO_PORTS)
    if stats.fresh_class_ports < 2:
        detail = None
        if stats.oldest_class_age_s is not None:
            detail = f"oldest class reading is {stats.oldest_class_age_s:.0f}s old"
        return PairLoopResult(world_id=world_id, pairs=(), reason=REASON_ALL_STALE, detail=detail)
    if stats.compatible_pairs_considered == 0:
        return PairLoopResult(world_id=world_id, pairs=(), reason=REASON_NO_COMPATIBLE_PAIRS)
    return PairLoopResult(world_id=world_id, pairs=(), reason=REASON_COMPATIBLE_BUT_UNROUTED)
