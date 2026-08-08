"""WO-BUILD-FIGHTER-AFFORDABILITY-DECISION-ENGINE — recommend-only afford_fighters."""

from __future__ import annotations

from tw2002_aiclient.priority_engine import (
    FIGHTER_SMALL_STACK,
    afford_fighters,
    fighter_buy_status_label,
)


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
    assert result.fighter_stack_cost is None


def test_afford_fighters_default_price_is_none_not_hypothesis():
    """Tip must not pretend Class-0 100cr is measured — inject price."""
    result = afford_fighters(credits=1000)
    assert result.recommendation == "price_unknown"


def test_afford_fighters_basic_can_buy():
    result = afford_fighters(credits=1000, fighter_unit_price=100)
    assert result.recommendation == "buy_fighters"
    assert result.can_afford is True
    assert result.fighter_stack_cost == FIGHTER_SMALL_STACK * 100
    assert result.discretionary == 1000
    assert "Sol" in result.reason or "Class-0" in result.reason


def test_afford_fighters_insufficient_credits():
    result = afford_fighters(credits=200, fighter_unit_price=100)
    assert result.recommendation == "insufficient_credits"
    assert result.can_afford is False
    assert result.fighter_stack_cost == 500
    assert result.discretionary == 200


def test_afford_fighters_trade_float_blocks_buy():
    result = afford_fighters(credits=600, trade_float=200, fighter_unit_price=100)
    assert result.recommendation == "insufficient_credits"
    assert result.can_afford is False
    assert result.discretionary == 400


def test_afford_fighters_trade_float_exceeds_credits():
    result = afford_fighters(credits=100, trade_float=500, fighter_unit_price=100)
    assert result.recommendation == "keep_trade_float"
    assert result.can_afford is False
    assert result.discretionary == -400


def test_afford_fighters_holds_upgrade_higher_priority():
    result = afford_fighters(
        credits=2000, hold_upgrade_quote=800, fighter_unit_price=100
    )
    assert result.recommendation == "upgrade_holds"
    assert result.can_afford is True
    assert "75" in result.reason or "priority" in result.reason


def test_afford_fighters_holds_not_affordable_so_buy_fighters():
    result = afford_fighters(
        credits=600, hold_upgrade_quote=900, fighter_unit_price=100
    )
    assert result.recommendation == "buy_fighters"
    assert result.can_afford is True


def test_afford_fighters_custom_stack_size_and_price():
    result = afford_fighters(
        credits=2000, fighter_unit_price=150, desired_count=10
    )
    assert result.recommendation == "buy_fighters"
    assert result.fighter_stack_cost == 1500
    assert result.can_afford is True


def test_afford_fighters_zero_trade_float_same_as_none():
    result_none = afford_fighters(credits=1000, trade_float=None, fighter_unit_price=100)
    result_zero = afford_fighters(credits=1000, trade_float=0, fighter_unit_price=100)
    assert result_none.recommendation == result_zero.recommendation
    assert result_none.discretionary == result_zero.discretionary


def test_afford_fighters_goals_label_map():
    assert fighter_buy_status_label("buy_fighters") == "can buy"
    assert fighter_buy_status_label(
        afford_fighters(credits=1000, fighter_unit_price=100).recommendation
    ) == "can buy"
    assert fighter_buy_status_label(
        afford_fighters(credits=200, fighter_unit_price=100).recommendation
    ) == "need credits"
    assert fighter_buy_status_label(
        afford_fighters(credits=None).recommendation
    ) == "price?"
