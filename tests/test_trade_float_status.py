"""WO-AICLIENT-BUILD-TRADE-FLOAT-STATUS-PRODUCER — status merge for working capital."""

from __future__ import annotations

import ast
from pathlib import Path

from tw2002_aiclient.trade_float_status import TRADE_FLOAT_KEY, TradeFloatScalars
from tw2002_aiclient.priority_engine import afford_fighters
from tw2002_aiclient.cockpit.goals import compose_goals_lines


def test_observe_merge_omit_until_known():
    scalars = TradeFloatScalars()
    assert scalars.merge({}) == {}
    scalars.observe(-1)
    assert scalars.merge({}) == {}
    scalars.observe(True)  # type: ignore[arg-type]
    assert scalars.merge({}) == {}
    scalars.observe(1000)
    merged = scalars.merge({"credits": 5000})
    assert merged[TRADE_FLOAT_KEY] == 1000
    assert merged["credits"] == 5000


def test_merge_does_not_clobber_existing():
    scalars = TradeFloatScalars()
    scalars.observe(1000)
    merged = scalars.merge({TRADE_FLOAT_KEY: 2500})
    assert merged[TRADE_FLOAT_KEY] == 2500


def test_zero_trade_float_is_valid_observe():
    scalars = TradeFloatScalars()
    scalars.observe(0)
    assert scalars.merge({})[TRADE_FLOAT_KEY] == 0


def test_observe_then_afford_fighters_respects_float():
    scalars = TradeFloatScalars()
    scalars.observe(200)
    status = scalars.merge({"credits": 600, "fighter_unit_price": 100})
    verdict = afford_fighters(
        credits=status["credits"],
        fighter_unit_price=status["fighter_unit_price"],
        trade_float=status[TRADE_FLOAT_KEY],
    )
    assert verdict.recommendation != "buy_fighters"
    lines = compose_goals_lines(status, width=40)
    assert lines  # never-raises compose path


def test_no_default_seeded_at_module_level():
    import tw2002_aiclient.trade_float_status as mod

    assert not hasattr(mod, "DEFAULT_TRADE_FLOAT")
    assert TradeFloatScalars().merge({}) == {}


def test_app_wraps_trade_float_scalars():
    src = Path("tw2002_aiclient/app.py").read_text(encoding="utf-8")
    assert "trade_float_scalars.wrap" in src
    assert "_observe_trade_float" in src
    assert ast.parse(src) is not None


def test_screens_constructs_trade_float_scalars():
    src = Path("tw2002_aiclient/screens.py").read_text(encoding="utf-8")
    assert "TradeFloatScalars" in src
    assert "trade_float_scalars" in src
