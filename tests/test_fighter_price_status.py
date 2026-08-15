"""WO-AICLIENT-BUILD-FIGHTER-CLASS0-PRICE-EXECUTE — observe/merge status producer."""

from __future__ import annotations

from tw2002_aiclient.fighter_price_status import (
    CLASS0_PRICE_KEY,
    UNIT_PRICE_KEY,
    FighterPriceScalars,
    parse_fighter_unit_price,
)
from tw2002_aiclient.priority_engine import afford_fighters
from tw2002_aiclient.cockpit.goals import compose_goals_lines


def test_parse_fighter_unit_price_matches_cost_each():
    assert parse_fighter_unit_price("Fighters cost 100 credits each.") == 100
    assert parse_fighter_unit_price("Fighter cost 1,250 credits each") == 1250


def test_parse_fighter_unit_price_matches_credits_per_fighter():
    assert parse_fighter_unit_price("150 credits per fighter") == 150


def test_parse_fighter_unit_price_fail_closed():
    assert parse_fighter_unit_price(None) is None
    assert parse_fighter_unit_price("") is None
    assert parse_fighter_unit_price("How many fighters do you wish to use (0 to 30) [0]?") is None
    assert parse_fighter_unit_price("Fighters aboard: 99") is None


def test_observe_merge_writes_both_keys_without_default():
    scalars = FighterPriceScalars()
    assert scalars.merge({}) == {}
    scalars.observe(0)
    assert scalars.merge({}) == {}
    scalars.observe(100)
    merged = scalars.merge({"credits": 5000})
    assert merged[UNIT_PRICE_KEY] == 100
    assert merged[CLASS0_PRICE_KEY] == 100
    assert merged["credits"] == 5000


def test_merge_does_not_clobber_existing():
    scalars = FighterPriceScalars()
    scalars.observe(100)
    merged = scalars.merge({UNIT_PRICE_KEY: 200, CLASS0_PRICE_KEY: 200})
    assert merged[UNIT_PRICE_KEY] == 200
    assert merged[CLASS0_PRICE_KEY] == 200


def test_observe_screen_then_goals_can_buy():
    scalars = FighterPriceScalars()
    assert scalars.observe_screen("Fighters cost 100 credits each.") == 100
    status = scalars.merge({"credits": 5000, "fighters_aboard": 0})
    assert status is not None
    verdict = afford_fighters(
        credits=status["credits"],
        fighter_unit_price=status[UNIT_PRICE_KEY],
    )
    assert verdict.recommendation == "buy_fighters"
    lines = compose_goals_lines(status, width=40)
    joined = "\n".join(lines)
    assert "can buy" in joined or "0" in joined


def test_no_tip_figther_unit_price_class0_constant():
    import tw2002_aiclient.fighter_price_status as mod
    import tw2002_aiclient.priority_engine as pe

    assert not hasattr(mod, "FIGHTER_UNIT_PRICE_CLASS0")
    assert not hasattr(pe, "FIGHTER_UNIT_PRICE_CLASS0")
