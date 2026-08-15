"""Pins for WO-BUILD-DECISIONS-PANEL-TRACE-PRODUCER — autopilot_trace producer."""

from __future__ import annotations

from tw2002_aiclient import chain_search, chains
from tw2002_aiclient.chain_status import ChainScalars
from tw2002_aiclient.cockpit.decisions import compose_decisions_lines
from tw2002_aiclient.decisions_status import (
    AUTOPILOT_TRACE_KEY,
    DecisionScalars,
    build_autopilot_trace,
)
from tw2002_aiclient.focus_status import FocusScalars, recommend_focus_candidates

_VITALS = {"turns_left": 100, "credits": 5000}


def _hop(frm: int, to: int) -> chains.TradeHop:
    return chains.TradeHop(frm=frm, to=to, commodity="Fuel Ore", margin=50.0, turns=1)


def _chain(sectors: list[int], *, cr_per_turn: float = 50.0) -> chains.ProfitChain:
    hops = tuple(_hop(sectors[i], sectors[i + 1]) for i in range(len(sectors) - 1))
    return chains.ProfitChain(
        sectors=tuple(sectors),
        hops=hops,
        overall_profit=100.0,
        turns=len(hops),
        cr_per_turn=cr_per_turn,
        cr_per_execution=100.0,
    )


def _result(*, chains_=(), reason=None):
    return chain_search.ProfitChainResult(
        world_id="w",
        chains=tuple(chains_),
        reason=reason,
    )


def test_trace_maps_ev_per_turn_to_ev_cr_per_turn():
    """Accept — DECISIONS field name is ev_cr_per_turn, not FOCUS's ev_per_turn."""
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=80.0)]))
    status = {"hud": {"sector": {"value": 51, "age_s": 0.0}}, **_VITALS}
    focus_first = FocusScalars(cs).merge(status)
    trace = build_autopilot_trace(focus_first, chain_scalars=cs)
    assert trace["candidates"]
    top = trace["candidates"][0]
    assert top["kind"] == "run_chain"
    assert top["ev_cr_per_turn"] == 80.0
    assert "ev_per_turn" not in top
    assert top["gated"] is False
    assert top["rationale"]


def test_chosen_is_first_ungated_in_focus_order():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=80.0)]))
    status = {"hud": {"sector": {"value": 51, "age_s": 0.0}}, **_VITALS}
    focus = FocusScalars(cs).merge(status)
    trace = build_autopilot_trace(focus, chain_scalars=cs)
    assert trace["chosen"] == "run_chain"
    assert focus["focus"]["candidates"][0]["kind"] == "run_chain"


def test_decision_scalars_merge_does_not_clobber_existing_trace():
    prior = {"chosen": "explore", "candidates": [{"kind": "explore", "gated": False}]}
    status = {AUTOPILOT_TRACE_KEY: prior, **_VITALS}
    merged = DecisionScalars().merge(status)
    assert merged[AUTOPILOT_TRACE_KEY] is prior


def test_decision_scalars_wrap_composes_with_focus():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=80.0)]))
    base = {"hud": {"sector": {"value": 51, "age_s": 0.0}}, **_VITALS}
    provider = DecisionScalars(cs).wrap(FocusScalars(cs).wrap(lambda: dict(base)))
    snap = provider()
    assert snap["focus"]["candidates"][0]["kind"] == "run_chain"
    assert snap[AUTOPILOT_TRACE_KEY]["chosen"] == "run_chain"
    lines = compose_decisions_lines(snap, width=48)
    assert any("★" in ln and "Trade chain" in ln for ln in lines)


def test_gated_upgrade_never_chosen():
    status = {"stardock_found": True, "stardock_sectors": [1], **_VITALS}
    # ship prices unmet → upgrade gated; explore typically ungated first
    cands = recommend_focus_candidates(status, chain_scalars=ChainScalars())
    assert any(c["kind"] == "upgrade" and c["gated"] for c in cands)
    focus = {"focus": {"candidates": cands}}
    trace = build_autopilot_trace(focus)
    assert trace["chosen"] != "upgrade"
    if trace["chosen"] is not None:
        chosen_row = next(c for c in trace["candidates"] if c["kind"] == trace["chosen"])
        assert chosen_row["gated"] is False


def test_producer_never_raises_on_hostile_status():
    assert build_autopilot_trace(None) == {"chosen": None, "candidates": []}
    assert build_autopilot_trace("bogus")["candidates"] == []
    assert DecisionScalars().merge(None) is None
