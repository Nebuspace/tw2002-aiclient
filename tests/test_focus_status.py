"""Pins for WO-PRIORITY-ENGINE-FOCUS-WIRE — FOCUS status payload producer."""

from __future__ import annotations

from tw2002_aiclient import chain_search, chains
from tw2002_aiclient.chain_status import ChainScalars
from tw2002_aiclient.cockpit.focus import compose_focus_lines
from tw2002_aiclient.focus_status import FocusScalars, recommend_focus_candidates


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


def test_focus_run_chain_tops_when_executable_chain_exists():
    """Accept #1 — executable priced cycle → ungated run_chain on top."""
    cs = ChainScalars()
    local = _chain([50, 51, 52, 50], cr_per_turn=80.0)
    cs.update(_result(chains_=[local]))
    status = {"hud": {"sector": {"value": 51, "age_s": 0.0}}}
    cands = recommend_focus_candidates(status, chain_scalars=cs)
    assert cands
    assert cands[0]["kind"] == "run_chain"
    assert cands[0]["gated"] is False
    assert cands[0]["ev_per_turn"] == 80.0
    merged = FocusScalars(cs).merge(status)
    assert merged["focus"]["candidates"][0]["kind"] == "run_chain"
    lines = compose_focus_lines(merged, width=40)
    assert any("Trade chain" in ln for ln in lines)


def test_focus_explore_when_no_executable_chain():
    """Accept #2 — no chains → explore candidate present."""
    cands = recommend_focus_candidates({}, chain_scalars=ChainScalars())
    kinds = [c["kind"] for c in cands]
    assert "explore" in kinds
    assert "run_chain" not in kinds


def test_focus_upgrade_omitted_when_stardock_unknown():
    """Accept #3 — StarDock unknown → upgrade omitted (not gated noise)."""
    cands = recommend_focus_candidates({}, chain_scalars=ChainScalars())
    assert all(c["kind"] != "upgrade" for c in cands)


def test_focus_upgrade_gated_when_stardock_known_but_holds_unknown():
    status = {"stardock_found": True, "stardock_sectors": [1]}
    cands = recommend_focus_candidates(status, chain_scalars=ChainScalars())
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is True
    assert "empty holds" in (upgrade.get("gate_reason") or "")


def test_focus_merge_does_not_clobber_existing_payload():
    fs = FocusScalars()
    prior = {"focus": {"candidates": [{"kind": "explore", "gated": False}]}}
    assert fs.merge(prior)["focus"] is prior["focus"]


def test_compose_focus_lines_nonempty_on_merged_status():
    """Accept #4."""
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([10, 11, 12, 10])]))
    merged = FocusScalars(cs).merge({"hud": {"sector": {"value": 10}}})
    lines = compose_focus_lines(merged, width=40)
    assert lines and lines[0] != "—"
    assert any("Trade chain" in ln or "Explore" in ln for ln in lines)
