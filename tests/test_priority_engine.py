"""Priority engine — RT travel + stay-vs-leave (WO-PRIORITY-ENGINE-KERNEL)."""

from tw2002_aiclient.priority_engine import (
    compute_return_path,
    hops_of_path,
    stay_vs_leave_upgrade,
    travel_cost_rt_turns,
    upgrade_gate_while_chaining,
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
    assert leave is True
    assert reason.startswith("leave for upgrade")


def test_upgrade_gate_fail_closed_without_return_path():
    gated, reason, ev, rt = upgrade_gate_while_chaining(
        chain_cr_per_turn=550.0,
        upgrade_extra_cr_per_turn=200.0,
        upgrade_payback=15.0,
        hops_to_stardock=8,
        hops_return_to_work=None,
        turns_per_warp=3,
        productive_turns=1950,
    )
    assert gated is True
    assert "return path" in (reason or "")
    assert ev is None
    assert rt is None
