"""Pins for WO-PRIORITY-ENGINE-FOCUS-WIRE — FOCUS status payload producer."""

from __future__ import annotations

from tw2002_aiclient import chain_search, chains
from tw2002_aiclient.chain_status import ChainScalars
from tw2002_aiclient.cockpit.focus import compose_focus_lines
from tw2002_aiclient.focus_status import FocusScalars, recommend_focus_candidates

# Catalog #1 must be met so lower-weight overlays / EV ranking are visible.
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


def test_focus_run_chain_tops_when_executable_chain_exists():
    """Accept #1 — executable priced cycle → ungated run_chain on top."""
    cs = ChainScalars()
    local = _chain([50, 51, 52, 50], cr_per_turn=80.0)
    cs.update(_result(chains_=[local]))
    status = {"hud": {"sector": {"value": 51, "age_s": 0.0}}, **_VITALS}
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
    """Ship/hold quotes unmet → catalog gate (not empty-holds) while StarDock known."""
    status = {"stardock_found": True, "stardock_sectors": [1], **_VITALS}
    cands = recommend_focus_candidates(status, chain_scalars=ChainScalars())
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is True
    assert "ship prices" in (upgrade.get("gate_reason") or "")


def test_focus_overlay_explore_beats_chain_when_ship_prices_unmet():
    """Unmet weight-80 ship prices → explore sorts above executable chain EV."""
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=80.0)]))
    status = {
        "hud": {"sector": {"value": 51, "age_s": 0.0}},
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 0,
        **_VITALS,
    }
    cands = recommend_focus_candidates(status, chain_scalars=cs)
    assert cands[0]["kind"] == "explore"
    assert cands[0].get("priority_weight") == 80
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is True
    assert "ship prices" in (upgrade.get("gate_reason") or "")
    lines = compose_focus_lines(
        {"focus": {"candidates": cands}}, width=40
    )
    assert any("⊘" in ln and "Upgrade" in ln for ln in lines)


def test_focus_overlay_clears_when_catalog_met():
    """Priced ships + hold label → normal EV ranking; upgrade RT-gated while chaining."""
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=80.0)]))
    status = {
        "hud": {
            "sector": {"value": 51, "age_s": 0.0},
            "cargo": {"value": 3, "age_s": 0.0},
        },
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 4,
        "hold_price_label": "1,200cr",
        **_VITALS,
    }
    cands = recommend_focus_candidates(status, chain_scalars=cs)
    assert cands[0]["kind"] == "run_chain"
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    # Executable chain → fail-closed without RT / upgrade economics.
    assert upgrade["gated"] is True
    assert "unknown" in (upgrade.get("gate_reason") or "")


def test_focus_upgrade_ungated_without_chain_when_catalog_met():
    """No executable chain → upgrade ungated once empty holds + catalog known."""
    status = {
        "hud": {"cargo": {"value": 3, "age_s": 0.0}},
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 4,
        "hold_price_label": "1,200cr",
        **_VITALS,
    }
    cands = recommend_focus_candidates(status, chain_scalars=ChainScalars())
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is False


def test_focus_upgrade_gated_empty_holds_when_catalog_met():
    status = {
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 2,
        "hold_price_label": "500cr",
        **_VITALS,
    }
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


def test_focus_stay_vs_leave_demotes_upgrade_behind_chain():
    """Accept — stay_vs_leave stay → upgrade gated; run_chain stays on top."""
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=500.0)]))
    status = {
        "hud": {
            "sector": {"value": 51, "age_s": 0.0},
            "cargo": {"value": 3, "age_s": 0.0},
        },
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 4,
        "hold_price_label": "1,200cr",
        "hops_to_stardock": 20,
        "hops_return_to_work": 20,
        "turns_per_warp": 1,
        "turns_left": 100,
        "turn_reserve": 0,
        "credits": 5000,
        # High headline EV, but RT forgone beats gain (stay).
        "upgrade_extra_cr_per_turn": 50.0,
        "upgrade_payback": 20.0,
    }
    cands = recommend_focus_candidates(status, chain_scalars=cs)
    assert cands[0]["kind"] == "run_chain"
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is True
    assert "stay trading" in (upgrade.get("gate_reason") or "")
    assert upgrade.get("travel_cost_rt") == 40  # (20+20)*1


def test_focus_leave_for_upgrade_when_gain_beats_rt():
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=100.0)]))
    status = {
        "hud": {
            "sector": {"value": 51, "age_s": 0.0},
            "cargo": {"value": 3, "age_s": 0.0},
        },
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 4,
        "hold_price_label": "1,200cr",
        "hops_to_stardock": 2,
        "hops_return_to_work": 2,
        "turns_per_warp": 1,
        "turns_left": 100,
        "turn_reserve": 0,
        "credits": 5000,
        "upgrade_extra_cr_per_turn": 400.0,
        "upgrade_payback": 5.0,
    }
    cands = recommend_focus_candidates(status, chain_scalars=cs)
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is False
    assert upgrade["ev_per_turn"] == 400.0


def test_focus_weight100_explore_beats_chain_when_turns_credits_unknown():
    """Catalog #1 unmet → explore weight-100 sorts above executable chain."""
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=80.0)]))
    status = {
        "hud": {"sector": {"value": 51, "age_s": 0.0}},
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 4,
        "hold_price_label": "1,200cr",
        # turns_left / credits intentionally omitted
    }
    cands = recommend_focus_candidates(status, chain_scalars=cs)
    assert cands[0]["kind"] == "explore"
    assert cands[0].get("priority_weight") == 100
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is True
    assert "turns/credits" in (upgrade.get("gate_reason") or "")


def test_focus_hops_return_from_warp_graph_via_compute_return_path():
    """``warp_graph`` + dock + work_sector → hops_return via compute_return_path."""
    cs = ChainScalars()
    cs.update(_result(chains_=[_chain([50, 51, 52, 50], cr_per_turn=80.0)]))
    # Linear: dock 1 — 2 — 50 (work). Return path length 3 → 2 hops.
    status = {
        "hud": {
            "sector": {"value": 50, "age_s": 0.0},
            "cargo": {"value": 3, "age_s": 0.0},
        },
        "stardock_found": True,
        "stardock_sectors": [1],
        "ship_prices_count": 4,
        "hold_price_label": "1,200cr",
        "warp_graph": {1: [2], 2: [1, 50], 50: [2]},
        "work_sector": 50,
        "hops_to_stardock": 2,
        "turns_per_warp": 1,
        "turns_left": 100,
        "turn_reserve": 0,
        "credits": 5000,
        "upgrade_extra_cr_per_turn": 400.0,
        "upgrade_payback": 5.0,
    }
    cands = recommend_focus_candidates(status, chain_scalars=cs)
    upgrade = next(c for c in cands if c["kind"] == "upgrade")
    assert upgrade["gated"] is False
    assert upgrade.get("travel_cost_rt") == 4  # (2+2)*1
