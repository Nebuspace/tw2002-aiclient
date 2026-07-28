"""WO-CHAIN-NPORT-WIRE — the N-port wire (`chain_search.recompute`).

No network, no daemon, no sends: pure world-model reads through
`trade_adapter.build_trade_hops` into `chains.find_profit_chains_with_note`.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from tw2002_aiclient import chain_search, chains, trade_adapter, world_model

NOW = datetime.datetime(2026, 7, 28, 4, 0, tzinfo=datetime.timezone.utc)
CLOCK = lambda: NOW  # noqa: E731
W = "test+nport"


def _row(name, status, pct, amount=1000):
    return {"name": name, "status": status, "amount": amount, "pct": pct}


def _up(tmp_path, sector_id, warps, commodities=None):
    record = {"sector_id": sector_id, "warps": list(warps)}
    if commodities is not None:
        record["port"] = {
            "commodities": commodities,
            "last_seen_ts": world_model._now_iso(CLOCK),
        }
    world_model.upsert_sector(W, record, state_dir=tmp_path, now=CLOCK)


def _triangle(tmp_path):
    """A genuine THREE-port cycle. `frm` SELLS -> `to` BUYS, so:
    10 sells Equipment -> 12 buys it; 12 sells Organics -> 11 buys it;
    11 sells Fuel Ore -> 10 buys it.  Cycle: 10 -> 12 -> 11 -> 10.

    Deliberately not a mutually-complementary PAIR: this shape is
    invisible to `chain_detect`'s 2-port set-intersection and is the whole
    reason the N-port finder exists."""
    _up(tmp_path, 10, (11, 12), [_row("Equipment", "selling", 100), _row("Fuel Ore", "buying", 0)])
    _up(tmp_path, 11, (10, 12), [_row("Fuel Ore", "selling", 100), _row("Organics", "buying", 0)])
    _up(tmp_path, 12, (10, 11), [_row("Organics", "selling", 100), _row("Equipment", "buying", 0)])


# -- the headline: does the wire actually carry a >2-port cycle? ------------


def test_three_port_cycle_is_found_end_to_end(tmp_path: Path):
    """The wire, proven. `chains.py` shipped this search complete and
    callerless; this is the first product-reachable path into it."""
    _triangle(tmp_path)
    result = chain_search.recompute(W, state_dir=tmp_path, now=CLOCK)

    assert result.reason is None
    assert len(result.chains) >= 1
    best = result.chains[0]
    # Strictly MORE than the 2-port pair path -- a pair would be 2 hops.
    assert len(best.hops) == 3
    assert best.sectors[0] == best.sectors[-1], "cycle must be closed"
    assert set(best.sectors) == {10, 11, 12}
    assert best.cr_per_turn > 0


def test_found_result_is_not_truncated(tmp_path: Path):
    _triangle(tmp_path)
    result = chain_search.recompute(W, state_dir=tmp_path, now=CLOCK)
    assert result.truncated is False
    assert result.adapter_note is None
    assert result.search_note is None


# -- honest empties, one per typed reason ----------------------------------


def test_never_explored_world_reports_no_world_model(tmp_path: Path):
    result = chain_search.recompute("test+never-explored", state_dir=tmp_path, now=CLOCK)
    assert result.chains == ()
    assert result.reason == chain_search.REASON_NO_WORLD_MODEL


def test_known_sectors_without_priced_ports_report_no_tradeable_hops(tmp_path: Path):
    """Sectors exist, warps exist, no port commerce data -> the world IS
    explored, so `no_world_model` would be a false statement about it."""
    _up(tmp_path, 30, (31,))
    _up(tmp_path, 31, (30,))
    result = chain_search.recompute(W, state_dir=tmp_path, now=CLOCK)
    assert result.chains == ()
    assert result.reason == chain_search.REASON_NO_TRADEABLE_HOPS


def test_hops_that_never_close_report_no_closed_cycle(tmp_path: Path):
    """One compatible direction only -- a hop exists, but nothing returns,
    so there is no cycle. Distinct from 'no hops at all'."""
    _up(tmp_path, 40, (41,), [_row("Equipment", "selling", 100)])
    _up(tmp_path, 41, (40,), [_row("Equipment", "buying", 0)])
    result = chain_search.recompute(W, state_dir=tmp_path, now=CLOCK)
    assert result.chains == ()
    assert result.reason == chain_search.REASON_NO_CLOSED_CYCLE


# -- the load-bearing design: two truncations, carried separately ----------


def test_search_budget_truncation_is_reported_on_a_FOUND_result(tmp_path: Path):
    """A budget that fires must not be silently swallowed just because
    chains were found -- a partial list is not an exhaustive one."""
    _triangle(tmp_path)
    result = chain_search.recompute(W, state_dir=tmp_path, now=CLOCK, max_search_steps=1)
    assert result.search_note is not None
    assert result.truncated is True
    # adapter did NOT truncate -- the two must not be conflated
    assert result.adapter_note is None


def test_truncated_EMPTY_does_not_claim_absence(tmp_path: Path):
    """The sharp one. An empty result from a truncated search has NOT
    established that no cycle exists -- only that none turned up in the
    fraction searched. The payload must say so, or a caller reports
    'no profitable cycle here' on the strength of an exhausted budget."""
    _triangle(tmp_path)
    result = chain_search.recompute(W, state_dir=tmp_path, now=CLOCK, max_search_steps=1, min_hops=99)

    assert result.chains == ()
    assert result.search_note is not None
    assert result.truncated is True
    assert result.detail is not None
    assert "absence is not established" in result.detail


def test_adapter_and_search_notes_are_independent_fields(tmp_path: Path):
    """They are different claims -- 'I did not consider every hop' vs
    'I did not finish searching the hops I had'. Folding them into one
    string would make a doubly-partial result read as singly-partial."""
    _triangle(tmp_path)
    cfg = trade_adapter.TradeAdapterConfig(max_hops=1)
    result = chain_search.recompute(
        W, state_dir=tmp_path, now=CLOCK, config=cfg, max_search_steps=1
    )
    assert result.adapter_note is not None, "edge cap should have truncated"
    # Distinct objects, distinct wording -- not the same note twice.
    assert result.adapter_note != result.search_note


# -- constant-drift pin ----------------------------------------------------


def test_min_hops_default_tracks_the_canon_execute_floor():
    """`recompute`'s discovery floor is bound to `chains`' canon-backed
    execute-floor constant, not a literal `2`. If canon moves the floor and
    only one of them follows, this fails rather than silently diverging."""
    import inspect

    default = inspect.signature(chain_search.recompute).parameters["min_hops"].default
    assert default == chains.MIN_CHAIN_LINKS_TO_EXECUTE


def test_result_is_frozen():
    r = chain_search.ProfitChainResult(world_id="w", chains=())
    with pytest.raises(Exception):
        r.world_id = "other"  # type: ignore[misc]
