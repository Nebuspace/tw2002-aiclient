"""Tests for reroute-vs-fight EV ranking kernel."""

from __future__ import annotations

from tw2002_aiclient.reroute_vs_fight import (
    compare_reroute_vs_fight,
    extra_hops,
    reroute_turn_cost,
    toll_ev_to_status,
)
from tw2002_aiclient.session import fighter_toll_policy


def test_extra_hops_never_invents():
    assert extra_hops(None, 5) is None
    assert extra_hops(2, None) is None
    assert extra_hops(2, 5) == 3
    assert extra_hops(5, 2) == 0


def test_reroute_turn_cost():
    assert reroute_turn_cost(2, 3) == 6
    assert reroute_turn_cost(None, 3) is None
    assert reroute_turn_cost(2, None) is None
    assert reroute_turn_cost(2, 0) is None


def test_prefer_reroute_when_cheaper_and_below_gate():
    ev = compare_reroute_vs_fight(
        extra_hops=1,
        turns_per_warp=3,
        expected_fight_turns=20.0,
        own_fighters=10,
        enemy_fighters=5,  # share=0.666 < 0.90
    )
    assert ev.preferred == "reroute"
    assert ev.reroute_turns == 3
    assert ev.below_auto_attack_gate is True
    assert ev.gated is False
    assert ev.force_share is not None and ev.force_share < 0.90


def test_incomplete_costs_fail_closed():
    ev = compare_reroute_vs_fight(
        own_fighters=90,
        enemy_fighters=10,
    )
    assert ev.preferred == "unknown"
    assert ev.gated is True
    assert ev.gate_reason == "costs_incomplete"


def test_pvp_hard_stop():
    ev = compare_reroute_vs_fight(
        extra_hops=1,
        turns_per_warp=3,
        expected_fight_turns=1.0,
        own_fighters=100,
        enemy_fighters=1,
        is_pvp=True,
    )
    assert ev.preferred == "unknown"
    assert ev.gated is True
    assert ev.gate_reason == "pvp_hard_stop"


def test_missing_counts_fail_closed():
    ev = compare_reroute_vs_fight(
        extra_hops=1,
        turns_per_warp=3,
        expected_fight_turns=50.0,
        own_fighters=10,
        enemy_fighters=None,
    )
    assert ev.gate_reason == "counts_incomplete"
    assert ev.gated is True


def test_fight_cheaper_but_below_gate_stays_gated():
    ev = compare_reroute_vs_fight(
        extra_hops=10,
        turns_per_warp=3,  # 30t reroute
        expected_fight_turns=5.0,
        own_fighters=10,
        enemy_fighters=5,
    )
    assert ev.preferred == "fight"
    assert ev.gated is True
    assert ev.gate_reason == "below_auto_attack_gate"


def test_at_gate_ranks_fight_without_sending():
    ev = compare_reroute_vs_fight(
        extra_hops=10,
        turns_per_warp=3,
        expected_fight_turns=5.0,
        own_fighters=95,
        enemy_fighters=5,  # share=0.95 ≥ 0.90, enemy≤3? 5 > 3 band → below gate
    )
    # enemy 5 > band 3 → still below auto-Attack
    assert ev.below_auto_attack_gate is True

    ev2 = compare_reroute_vs_fight(
        extra_hops=10,
        turns_per_warp=3,
        expected_fight_turns=5.0,
        own_fighters=97,
        enemy_fighters=3,  # share=0.97, band ok
    )
    assert ev2.below_auto_attack_gate is False
    assert ev2.preferred == "fight"
    assert ev2.gated is False


def test_ev_does_not_alter_decide_encounter():
    """Pin: ranking module must not be imported by the live toll rail."""
    import tw2002_aiclient.reroute_vs_fight as rvf

    src = open(fighter_toll_policy.__file__, encoding="utf-8").read()
    assert "reroute_vs_fight" not in src
    state = fighter_toll_policy.EncounterState(True, 10, 5, False)
    d = fighter_toll_policy.decide_encounter(state)
    assert d.key == "R"  # below gate → Retreat, unchanged by EV module existence
    assert rvf.compare_reroute_vs_fight is not None


def test_toll_ev_to_status_shape():
    ev = compare_reroute_vs_fight(
        extra_hops=1,
        turns_per_warp=3,
        expected_fight_turns=20.0,
        own_fighters=10,
        enemy_fighters=5,
    )
    d = toll_ev_to_status(ev)
    assert d["preferred"] == "reroute"
    assert "rationale" in d
