"""Priority engine — RT travel + stay-vs-leave tests (WO-PRIORITY-ENGINE-0)."""

from twclient.priority_engine import (
    compute_return_path,
    hops_of_path,
    recommend_actions,
    stay_vs_leave_upgrade,
    travel_cost_rt_turns,
)


def test_travel_cost_rt_is_out_plus_return():
    assert travel_cost_rt_turns(5, 5, turns_per_warp=3) == 30
    assert travel_cost_rt_turns(0, 0, turns_per_warp=6) == 0
    assert hops_of_path((10, 20, 30)) == 2
    assert hops_of_path((10,)) == 0
    assert hops_of_path(None) is None


def test_return_path_uses_known_graph():
    graph = {1: (2,), 2: (1, 3), 3: (2, 99), 99: (3,)}
    path = compute_return_path(graph, 99, 1)
    assert path == (99, 3, 2, 1)
    assert hops_of_path(path) == 3


def test_stay_when_rt_forgone_beats_upgrade_gain():
    leave, reason = stay_vs_leave_upgrade(
        chain_cr_per_turn=500.0,
        upgrade_extra_cr_per_turn=50.0,
        travel_cost_rt=40,
        payback=20.0,
        productive_turns=100,
    )
    # remaining_after = 100-40-20 = 40; gain = 50*40 = 2000; forgone = 500*40 = 20000
    assert leave is False
    assert reason.startswith("stay trading")


def test_leave_when_upgrade_gain_beats_rt_forgone():
    leave, reason = stay_vs_leave_upgrade(
        chain_cr_per_turn=100.0,
        upgrade_extra_cr_per_turn=400.0,
        travel_cost_rt=10,
        payback=5.0,
        productive_turns=100,
    )
    # remaining = 85; gain = 400*85 = 34000; forgone = 100*10 = 1000
    assert leave is True
    assert reason.startswith("leave for upgrade")


def test_recommend_gates_upgrade_without_return_path_while_chaining():
    rec = recommend_actions(
        chain_cr_per_turn=550.0,
        chain_cycle_turns=10,
        at_chain_start=True,
        upgrade_extra_cr_per_turn=200.0,
        upgrade_payback=15.0,
        upgrade_ship_name="Merchant Cruiser",
        hops_to_stardock=8,
        hops_return_to_work=None,  # unknown RT
        turns_per_warp=3,
        turns_left=2000,
        turn_reserve=50,
        explore_available=True,
    )
    upgrade = next(s for s in rec.ranked if s.kind == "upgrade")
    assert upgrade.gated is True
    assert "return path" in (upgrade.gate_reason or "")
    assert rec.focus is not None
    assert rec.focus.kind == "run_chain"


def test_recommend_stay_on_chain_when_rt_too_expensive():
    rec = recommend_actions(
        chain_cr_per_turn=550.0,
        chain_cycle_turns=10,
        at_chain_start=True,
        upgrade_extra_cr_per_turn=80.0,
        upgrade_payback=20.0,
        upgrade_ship_name="Merchant Cruiser",
        hops_to_stardock=10,
        hops_return_to_work=10,
        turns_per_warp=3,  # RT = 60t
        turns_left=500,
        turn_reserve=50,
        explore_available=False,
    )
    assert rec.focus is not None
    assert rec.focus.kind == "run_chain"
    assert rec.stay_vs_leave is not None
    assert rec.stay_vs_leave.startswith("stay")


def test_recommend_upgrade_when_payback_and_rt_beat_chain():
    rec = recommend_actions(
        chain_cr_per_turn=100.0,
        chain_cycle_turns=10,
        at_chain_start=True,
        upgrade_extra_cr_per_turn=400.0,
        upgrade_payback=5.0,
        upgrade_ship_name="Corporate Flagship",
        hops_to_stardock=2,
        hops_return_to_work=2,
        turns_per_warp=2,  # RT = 8t
        turns_left=500,
        turn_reserve=50,
        explore_available=True,
    )
    assert rec.focus is not None
    assert rec.focus.kind == "upgrade"
    assert rec.focus.travel_cost_rt == 8
    assert rec.stay_vs_leave is not None
    assert rec.stay_vs_leave.startswith("leave")


def test_recommend_gates_unknown_stardock_path():
    rec = recommend_actions(
        chain_cr_per_turn=None,
        upgrade_extra_cr_per_turn=200.0,
        upgrade_payback=10.0,
        hops_to_stardock=None,
        hops_return_to_work=None,
        turns_left=1000,
        explore_available=True,
        require_rt_when_chain_active=True,
    )
    upgrade = next(s for s in rec.ranked if s.kind == "upgrade")
    assert upgrade.gated is True
    assert "StarDock" in (upgrade.gate_reason or "")
    assert rec.focus.kind == "explore"
