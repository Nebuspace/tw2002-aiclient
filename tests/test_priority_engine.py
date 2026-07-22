"""Priority engine — RT travel + stay-vs-leave tests (WO-PRIORITY-ENGINE-0)."""

from twclient.priority_engine import (
    FIGHTER_SMALL_STACK,
    FIGHTER_UNIT_PRICE_CLASS0,
    FighterAffordability,
    afford_fighters,
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
        chain_link_count=5,
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
        chain_link_count=5,
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
        chain_link_count=5,
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


def test_run_chain_gated_below_three_links():
    rec = recommend_actions(
        chain_cr_per_turn=400.0,
        chain_cycle_turns=8,
        chain_link_count=2,
        turns_left=2000,
        explore_available=True,
    )
    chain = next(s for s in rec.ranked if s.kind == "run_chain")
    assert chain.gated is True
    assert "≥3-link" in (chain.gate_reason or "")
    assert rec.focus.kind == "explore"


def test_three_link_prefers_earn_for_fighters_and_holds():
    """At 3 links, grind the chain (cash for fighters/holds) — do not hunt first."""
    from twclient.priority_engine import prefer_search_over_earn

    prefer, reason = prefer_search_over_earn(chain_links=3, explore_available=True)
    assert prefer is False
    assert "grind" in reason

    rec = recommend_actions(
        chain_cr_per_turn=550.0,
        chain_cycle_turns=10,
        chain_link_count=3,
        turns_left=2000,
        explore_available=True,
    )
    chain = next(s for s in rec.ranked if s.kind == "run_chain")
    assert chain.gated is False
    assert rec.focus.kind == "run_chain"


def test_three_link_defers_ship_upgrade_until_four():
    """Ship hull waits for ≥4-link; 3-link cash targets fighters/holds."""
    rec = recommend_actions(
        chain_cr_per_turn=550.0,
        chain_cycle_turns=10,
        chain_link_count=3,
        at_chain_start=True,
        upgrade_extra_cr_per_turn=400.0,
        upgrade_payback=5.0,
        upgrade_ship_name="Corporate Flagship",
        hops_to_stardock=2,
        hops_return_to_work=2,
        turns_per_warp=2,
        turns_left=2000,
        turn_reserve=50,
        explore_available=False,
    )
    upgrade = next(s for s in rec.ranked if s.kind == "upgrade")
    assert upgrade.gated is True
    assert "ship deferred" in (upgrade.gate_reason or "")
    assert "≥4-link" in (upgrade.gate_reason or "")
    assert rec.focus.kind == "run_chain"


def test_four_link_allows_ship_upgrade_when_rt_beats_chain():
    rec = recommend_actions(
        chain_cr_per_turn=100.0,
        chain_cycle_turns=10,
        chain_link_count=4,
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


def test_five_link_prefers_earn_over_explore():
    rec = recommend_actions(
        chain_cr_per_turn=550.0,
        chain_cycle_turns=10,
        chain_link_count=5,
        turns_left=2000,
        explore_available=True,
    )
    assert rec.focus.kind == "run_chain"


# ---------------------------------------------------------------------------
# afford_fighters() — fighter affordability helper
# ---------------------------------------------------------------------------


def test_afford_fighters_unknown_credits_returns_price_unknown():
    result = afford_fighters(credits=None)
    assert result.recommendation == "price_unknown"
    assert result.can_afford is None
    assert result.fighter_stack_cost is None
    assert result.discretionary is None


def test_afford_fighters_unknown_unit_price_returns_price_unknown():
    result = afford_fighters(credits=5000, fighter_unit_price=None)
    assert result.recommendation == "price_unknown"
    assert result.can_afford is None
    assert result.discretionary == 5000


def test_afford_fighters_basic_can_buy():
    # 1000 credits, stack costs 5 × 100 = 500 — affordable
    result = afford_fighters(credits=1000)
    assert result.recommendation == "buy_fighters"
    assert result.can_afford is True
    assert result.fighter_stack_cost == FIGHTER_SMALL_STACK * FIGHTER_UNIT_PRICE_CLASS0
    assert result.discretionary == 1000
    assert "Sol" in result.reason or "Class-0" in result.reason


def test_afford_fighters_insufficient_credits():
    # 200 credits, stack = 500 — not affordable
    result = afford_fighters(credits=200)
    assert result.recommendation == "insufficient_credits"
    assert result.can_afford is False
    assert result.fighter_stack_cost == 500
    assert result.discretionary == 200


def test_afford_fighters_trade_float_blocks_buy():
    # 600 credits, but trade_float=200 → discretionary=400 < 500 stack
    result = afford_fighters(credits=600, trade_float=200)
    assert result.recommendation == "insufficient_credits"
    assert result.can_afford is False
    assert result.discretionary == 400


def test_afford_fighters_trade_float_exceeds_credits():
    # Credits below trade_float floor
    result = afford_fighters(credits=100, trade_float=500)
    assert result.recommendation == "keep_trade_float"
    assert result.can_afford is False
    assert result.discretionary == -400


def test_afford_fighters_holds_upgrade_higher_priority():
    # 2000 cr, stack=500, hold quote=800 — holds affordable → holds first
    result = afford_fighters(credits=2000, hold_upgrade_quote=800)
    assert result.recommendation == "upgrade_holds"
    assert result.can_afford is True
    assert "75" in result.reason or "priority" in result.reason


def test_afford_fighters_holds_not_affordable_so_buy_fighters():
    # 600 cr, stack=500, hold quote=900 — hold NOT affordable, buy fighters
    result = afford_fighters(credits=600, hold_upgrade_quote=900)
    assert result.recommendation == "buy_fighters"
    assert result.can_afford is True


def test_afford_fighters_custom_stack_size_and_price():
    # 10 fighters at 150 each = 1500; have 2000 → affordable
    result = afford_fighters(credits=2000, fighter_unit_price=150, desired_count=10)
    assert result.recommendation == "buy_fighters"
    assert result.fighter_stack_cost == 1500
    assert result.can_afford is True


def test_afford_fighters_zero_trade_float_same_as_none():
    result_none = afford_fighters(credits=1000, trade_float=None)
    result_zero = afford_fighters(credits=1000, trade_float=0)
    assert result_none.recommendation == result_zero.recommendation
    assert result_none.discretionary == result_zero.discretionary


def test_afford_fighters_goals_label_map():
    """Verify GOALS labels map correctly from recommendation strings."""
    label_map = {
        "buy_fighters": "can buy",
        "upgrade_holds": "holds first",
        "keep_trade_float": "need credits",
        "insufficient_credits": "need credits",
        "price_unknown": "price?",
    }
    # Affordable case → "can buy"
    r = afford_fighters(credits=1000)
    assert label_map.get(r.recommendation) == "can buy"

    # Insufficient → "need credits"
    r = afford_fighters(credits=200)
    assert label_map.get(r.recommendation) == "need credits"

    # Unknown credits → "price?"
    r = afford_fighters(credits=None)
    assert label_map.get(r.recommendation) == "price?"
