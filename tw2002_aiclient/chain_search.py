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

**NEVER the taught `L)chains` arm list.** A discovered, unpriced cycle
rendered there would be indistinguishable from a taught, human-armed macro
at the money-spending confirm gate -- the exact conflation
`chain_detect_view` was created to prevent. Same ruling applies here.

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


@dataclass(frozen=True)
class ProfitChainResult:
    """The one frozen result `recompute` returns.

    `chains` is already ranked by `chains.rank_chains` (hop-count desc, then
    cr/turn desc) and is non-empty exactly when `reason` is `None`.

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
    """
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

    return ProfitChainResult(
        world_id=world_id,
        chains=tuple(found),
        reason=None,
        adapter_note=adapter_note,
        search_note=search_note,
    )
