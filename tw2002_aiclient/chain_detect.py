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

Bridge to the listing surface only (`loops/list_view.format_loop_row`) --
NEVER `cockpit/chains.py` or its store. That popup's rows are the ARM
list (`app.py` -> `begin_arm_confirm` -> `y` -> `adapters.autoloop_start`,
the money-spending call); a discovered, unpriced pair loop rendered there
would be indistinguishable from a taught, human-armed macro at the arm
gate. This module's rows carry `source: _SOURCE_TAG` (`"detected"`) and NO
profit key at all -- they can only ever reach a read-only listing, never
the taught store. `format_coach_callout` (or equivalent) is explicitly out
of scope for this WO -- escalated to the hub, not built here.

Unit safety, REVISE (Samantha, see `as_library_rows`'s own docstring for
the full reasoning): a discovered pair loop must never render a fabricated
keystroke-step count (`format_loop_row`'s `steps` column means recorded/
mined MACRO steps -- a completely different unit from a pair loop's 2
HOPS), and the one genuinely-known number on the row (`pair.turns`) must
not be silently dropped just because `format_loop_row` has no dedicated
column for it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Callable, Optional

from tw2002_aiclient import trade_adapter
from tw2002_aiclient.loops import list_view

# Typed empty-reason vocabulary -- checked in this fixed precedence order
# by `recompute` below, each naming a genuinely different situation so an
# operator (or a future coach surface) never has to guess which one fired:
REASON_NO_WORLD_MODEL = "no_world_model"  # this world has never recorded a single sector
REASON_FEWER_THAN_TWO_PORTS = "fewer_than_two_ports"  # <2 sectors carry a usable class triple, any age
REASON_ALL_STALE = "all_stale"  # >=2 valid triples exist, but <2 are within the class staleness ceiling
REASON_NO_COMPATIBLE_PAIRS = "no_compatible_pairs"  # >=2 fresh ports, none posture-complementary
REASON_COMPATIBLE_BUT_UNROUTED = "compatible_but_unrouted"  # a compatible pair exists, no known route both ways

# `as_library_rows`'s row `source` tag. NOT one of `loops/store.py`'s
# SOURCE_VALUES ("recorded", "mined") -- a discovered pair loop is neither
# (never demonstrated at the keyboard, never ledger-mined) -- and never,
# under any future edit, lengthened past `list_view._SOURCE_W` (9): a wider
# tag shifts every discovered row's profit/steps columns out of alignment
# with every taught row in the same listing. Length-pinned in
# tests/test_chain_detect.py against the real constant, not a restated `9`.
_SOURCE_TAG = "detected"


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


def as_library_rows(result: PairLoopResult) -> list[str]:
    """Bridge `result.pairs` into `loops/list_view.format_loop_row` --
    a read-only listing row per pair, in `result`'s own (already ranked)
    order. Never the taught-macro store, never an arm surface -- see
    module docstring's hard prohibition.

    Two unit-safety rules a discovered pair loop must never break
    (Samantha REVISE on this WO's first draft, which emitted `"steps":
    2` and silently dropped `turns` -- see git history):

    * **No fabricated keystroke-step count.** `format_loop_row`'s
      `steps` column means recorded/mined MACRO steps
      (`loops/store.py`'s `_row`: `len(document["steps"])`, and
      `canon/engine/macros.md` §Schema: `steps[]` of `{input,
      wait_prompt, expected_post_class}`) -- a different UNIT from a
      pair loop's 2 HOPS. A `CandidatePair` was never recorded, so it
      has zero keystroke steps, not two. `steps` is therefore omitted
      from the row dict entirely, which `format_loop_row` already
      renders as the honest `"? steps"` -- its own docstring names this
      exact case: "Defensive only... It exists for a hand-built row."
      This IS that hand-built row.
    * **`pair.turns` must survive into the rendered string.** It is the
      one genuinely-known, never-fabricated number on this row (see
      `CandidatePair`'s own docstring). `format_loop_row` has no
      dedicated `turns` column (it reads `profit_per_turn`/
      `profit_per_action`, neither of which a margin-less pair loop
      carries), so it rides inside `name` -- the one field `list_view.py`
      documents as "padded but never truncated: it is the identity a
      human types to replay the macro". A discovered, unrecorded loop
      has no such identity to protect (there is nothing to type yet),
      so folding the turns figure into it costs this row nothing real.

    `source` is `_SOURCE_TAG` (`"detected"`) -- not one of
    `loops/store.py`'s `SOURCE_VALUES` (`"recorded"`, `"mined"`; these
    rows never pass through that reader, which only validates documents
    actually read off the taught-macro store) and deliberately never
    `"mined"` -- `mined` means ledger-derived with a `start_anchor` and
    mined stats, which a `CandidatePair` carries none of. No profit key
    is ever emitted -- `format_loop_row` already renders canon's
    em-dash for an absent profit, never a fabricated `0`; there is no
    margin to report in the first place (`CandidatePair` has no margin
    field)."""
    return [
        list_view.format_loop_row(
            {
                "name": f"{pair.sector_a}<->{pair.sector_b} ({pair.turns}t)",
                "source": _SOURCE_TAG,
            }
        )
        for pair in result.pairs
    ]
