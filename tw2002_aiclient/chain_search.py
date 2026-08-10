"""chain_search -- N-PORT profit-cycle recompute (WO-CHAIN-NPORT-WIRE).

The wire that was missing. `chains.py` has shipped a complete N-port cycle
finder since before the rebirth -- iterative DFS, cycle normalization,
`rank_chains`, a search budget, an execute-floor -- and `trade_adapter.
build_trade_hops` has shipped the priced edge-builder its own docstring
names as the intended feed. **Neither had a single non-test caller.**
Producer built, consumer built, no wire between them and none to any
surface. This module is that wire, and nothing more.

Relationship to `chain_detect.py`: that module is the **PAIR** loop -- two
ports, set-intersection, deliberately "no cycle search, no multi-hop chain,
no budget" (its words). This one is the general case: N ports, real DFS,
budgeted. They are siblings, not layers, and neither imports the other.
A pair loop is the cheapest shape; a chain is the general one.

Pure world-model read. ZERO sends, ZERO execution, no curses, no protocol
import, no session. Like `chain_detect`, it stops at the typed payload and
does not render -- `chain_search_view.format_profit_chain_lines` owns that.

**Never the recorded-macro arm list.** Since WO-CHAINS-TUI-FULL the
`L)chains` modal displays these cycles in a separate, `detected`-tagged
section; ADR-003 permits an exact chain to enter a distinct semantic
approve-scaffold flow, but it never enters recorded macro ``rows`` and this
producer never grants execution authority.

ADR-003 adds an explicit approval consumer without changing this module's
authority: this producer still only returns suggestions. The cockpit may hold
one exact fingerprint through a visible default-deny confirm, and the daemon
must recompute and match it before its guarded one-pass runner starts. No
finder call starts or selects a run here.

## Two truncations, carried separately -- the load-bearing design

This is a TWO-STAGE pipeline and each stage can silently truncate:

* `build_trade_hops` caps candidate edges (`config.max_hops`) and returns a
  note naming how many were dropped. Meaning: *I did not consider every hop*.
* `find_profit_chains_with_note` caps DFS frame-visits
  (`DEFAULT_MAX_SEARCH_STEPS`) and returns a note naming the budget.
  Meaning: *I did not finish searching the hops I was given*.

They are different claims and are kept in **different fields**. Folding them
into one string would make a doubly-partial result read as singly-partial,
and dropping either would let a truncated search present as exhaustive.

The sharpest consequence, and the reason `search_note` is carried even on
the EMPTY paths: **an empty result plus a truncation note is not a proof of
absence.** "No profitable cycle exists in this world" and "no profitable
cycle turned up in the fraction of the search I completed" are different
facts, and a caller that cannot distinguish them will report the first when
only the second is true.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Callable, Optional

from tw2002_aiclient import chains as chains_module
from tw2002_aiclient import trade_adapter, world_model

# Typed empty-reason vocabulary, checked in this fixed precedence order --
# each names a genuinely different situation, mirroring `chain_detect`'s
# five so an operator never has to guess which one fired:
REASON_NO_WORLD_MODEL = "no_world_model"  # this world has never recorded a sector
REASON_NO_TRADEABLE_HOPS = "no_tradeable_hops"  # sectors known; no priced, routable, direction-compatible hop
REASON_NO_CLOSED_CYCLE = "no_closed_cycle"  # hops exist; none of them close a profitable cycle

# Ranking (WO-FIX-CHAIN-DISCOVERY-RANK-SORT-ORDER + WO-BUILD-CHAIN-LONGEVITY-RANK-WIRE):
# canon discovery / explore keeps hop-count-first; earn / CLI credit-doubling
# surfaces ask for yield-first; longevity down-ranks near-depleted loops when
# holds + port amounts are known (port-economics H2). Default stays RANK_HOPS
# so L)chains / bubble callers do not silently flip.
RANK_HOPS = "hops"
RANK_YIELD = "yield"
RANK_LONGEVITY = "longevity"
_RANK_VALUES = frozenset({RANK_HOPS, RANK_YIELD, RANK_LONGEVITY})


@dataclass(frozen=True)
class ProfitChainResult:
    """The one frozen result `recompute` returns.

    `chains` is ranked per `recompute(..., rank=)` — default
    `chains.rank_chains` (hop-count desc, then cr/turn); earn surfaces
    may request `rank=RANK_YIELD` (`rank_chains_by_yield`); longevity
    surfaces may request `rank=RANK_LONGEVITY` (down-rank near-depleted
    via `chains.rank_chains_by_longevity` when holds + amounts known).
    Non-empty exactly when `reason` is `None`.

    `adapter_note` and `search_note` are independent and BOTH may be set.
    Neither is cleared on an empty result -- see the module docstring: a
    truncated search that found nothing has not established that nothing
    is there.
    """

    world_id: str
    chains: tuple[chains_module.ProfitChain, ...]
    reason: Optional[str] = None
    detail: Optional[str] = None
    adapter_note: Optional[str] = None
    search_note: Optional[str] = None

    @property
    def truncated(self) -> bool:
        """True if EITHER stage truncated. A caller that only wants to know
        "should I trust this as exhaustive?" asks this rather than
        re-deriving the two-field check and getting it half right."""
        return self.adapter_note is not None or self.search_note is not None


def recompute(
    world_id: str,
    *,
    state_dir=None,
    config: Optional[trade_adapter.TradeAdapterConfig] = None,
    now: Optional[Callable[[], datetime.datetime]] = None,
    min_hops: int = chains_module.MIN_CHAIN_LINKS_TO_EXECUTE,
    max_hops: Optional[int] = None,
    max_search_steps: int = chains_module.DEFAULT_MAX_SEARCH_STEPS,
    rank: str = RANK_HOPS,
    hold_count: Optional[int] = None,
    longevity_base: str = RANK_HOPS,
) -> ProfitChainResult:
    """Recompute N-port profit cycles for `world_id` from its current
    world-model state.

    Idempotent: given the same on-disk state and the same injected `now`,
    two calls return identical results. There is no wall-clock read here
    beyond what the caller supplies, and both stages are already
    deterministic in their ordering.

    `min_hops` defaults to `chains.MIN_CHAIN_LINKS_TO_EXECUTE` rather than a
    literal `2`, so the discovery floor cannot drift from the canon-backed
    execute-floor constant without one of them failing its own pin.

    `rank` selects the post-search order: ``RANK_HOPS`` (default, canon
    discovery), ``RANK_YIELD`` (earn / CLI), or ``RANK_LONGEVITY`` (H2
    depletion down-rank). Finder output is hop-ranked; yield/longevity
    re-rank without changing the search itself.

    Longevity ranking needs a positive ``hold_count`` plus world-model port
    ``amount`` fields. When evidence is incomplete, fail closed: keep the
    ``longevity_base`` order (``RANK_HOPS`` or ``RANK_YIELD``) and do **not**
    invent remaining-trades. ``longevity_base`` is ignored for non-longevity
    ranks.
    """
    if rank not in _RANK_VALUES:
        raise ValueError(
            f"unknown rank={rank!r}; expected one of {sorted(_RANK_VALUES)}"
        )

    hops, adapter_note = trade_adapter.build_trade_hops(
        world_id, state_dir=state_dir, config=config, now=now
    )

    if not hops:
        # Distinguish "never explored" from "explored, nothing tradeable" --
        # the same honest-empty split `chain_detect` makes. Only read the
        # world model on THIS branch: when hops exist the question is moot,
        # and a read we do not need is a read that can fail.
        known = len(world_model.all_sectors(world_id, state_dir=state_dir))
        return ProfitChainResult(
            world_id=world_id,
            chains=(),
            reason=REASON_NO_WORLD_MODEL if known == 0 else REASON_NO_TRADEABLE_HOPS,
            adapter_note=adapter_note,
        )

    found, search_note = chains_module.find_profit_chains_with_note(
        hops,
        min_hops=min_hops,
        max_hops=max_hops,
        max_search_steps=max_search_steps,
    )

    if not found:
        detail = None
        if search_note is not None:
            # Say the quiet part in the payload, not only in the note: this
            # empty is NOT an established absence.
            detail = "search truncated before completion -- absence is not established"
        return ProfitChainResult(
            world_id=world_id,
            chains=(),
            reason=REASON_NO_CLOSED_CYCLE,
            detail=detail,
            adapter_note=adapter_note,
            search_note=search_note,
        )

    if rank == RANK_YIELD:
        found = chains_module.rank_chains_by_yield(found)
    elif rank == RANK_LONGEVITY:
        found = _rank_found_by_longevity(
            found,
            world_id,
            state_dir=state_dir,
            hold_count=hold_count,
            longevity_base=longevity_base,
        )

    return ProfitChainResult(
        world_id=world_id,
        chains=tuple(found),
        reason=None,
        adapter_note=adapter_note,
        search_note=search_note,
    )


def _rank_found_by_longevity(
    found: list,
    world_id: str,
    *,
    state_dir,
    hold_count: Optional[int],
    longevity_base: str,
) -> list:
    """Apply ``rank_chains_by_longevity`` or fall back to base rank.

    Product wire for the previously test-only longevity helper (canon
    port-economics H2 — ranking / coaching, never autonomous rotation).
    """
    base = longevity_base if longevity_base in (RANK_HOPS, RANK_YIELD) else RANK_HOPS
    if base == RANK_YIELD:
        ordered = chains_module.rank_chains_by_yield(found)
        base_rank_name = "yield"
    else:
        ordered = list(found)  # finder already hop-ranked
        base_rank_name = "discovery"

    if isinstance(hold_count, bool) or not isinstance(hold_count, int) or hold_count <= 0:
        return ordered

    try:
        from tw2002_aiclient.chain_depletion import (
            chain_identity_key,
            ports_commodity_maps_from_records,
            predict_remaining_trades,
        )
    except Exception:  # noqa: BLE001 — ranking must not raise
        return ordered

    try:
        recs = world_model.query(
            world_id, lambda s: bool(s.get("port")), state_dir=state_dir
        )
        ports_by_sector = ports_commodity_maps_from_records(recs)
    except Exception:  # noqa: BLE001
        return ordered
    if not ports_by_sector:
        return ordered

    remaining_by_key: dict = {}
    for chain in ordered:
        key = chain_identity_key(chain)
        if key is None:
            continue
        remaining = predict_remaining_trades(
            chain,
            hold_count=hold_count,
            ports_by_sector=ports_by_sector,
        )
        if remaining is None:
            continue
        remaining_by_key[key] = remaining

    if not remaining_by_key:
        return ordered

    return chains_module.rank_chains_by_longevity(
        ordered, remaining_by_key, base_rank=base_rank_name
    )
