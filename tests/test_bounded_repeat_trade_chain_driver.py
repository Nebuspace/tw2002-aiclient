"""Unit tests for bounded-repeat trade-chain driver (mocked run_chain)."""

from __future__ import annotations

from tw2002_aiclient.bounded_repeat_trade_chain_driver import (
    DEFAULT_MAX_PASSES,
    STOP_PASS_COUNT,
    clamp_pass_count,
    run_bounded_repeat,
)
from tw2002_aiclient.loops.player import (
    HALT_FLOOR_REACHED,
    HALT_PROFIT_TARGET_REACHED,
)
from tw2002_aiclient.session.hud_tracking import ProfitSnapshot
from tw2002_aiclient.session.state_parser import OUTCOME_READ, CreditsSnapshot
from tw2002_aiclient.trade_driver import ChainRunResult


class _Caps:
    cash_floor = 1000
    turn_reserve = 10
    profit_target = None
    credits_stale_ms = 60_000


class _Session:
    def __init__(self, *, balance=5000, profit=0):
        self._balance = balance
        self._profit = profit

    def credits_snapshot(self):
        return CreditsSnapshot(outcome=OUTCOME_READ, balance=self._balance, age_s=0.0)

    def profit_snapshot(self):
        return ProfitSnapshot(outcome=OUTCOME_READ, profit=self._profit, age_s=0.0)


def _ok_result(delta=100):
    return ChainRunResult(
        completed=True,
        hops_completed=2,
        steps=4,
        credits_delta=delta,
        stop_reason="completed",
    )


def _halt_result(reason="realized_margin_below_floor:0:0"):
    return ChainRunResult(
        completed=False,
        hops_completed=0,
        steps=1,
        credits_delta=None,
        stop_reason=reason,
    )


def test_clamp_pass_count_default_and_ceiling():
    assert clamp_pass_count(DEFAULT_MAX_PASSES) == DEFAULT_MAX_PASSES
    assert clamp_pass_count(999) == 50
    try:
        clamp_pass_count(0)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_one_pass_preserves_completed_reason():
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        return _ok_result()

    result = run_bounded_repeat(
        _Session(),
        object(),
        world_id="w",
        turns_left_fn=lambda: 50,
        caps=_Caps(),
        should_abort=lambda: False,
        is_armed=lambda: True,
        max_passes=1,
        run_chain_fn=fake_run,
    )
    assert calls["n"] == 1
    assert result.completed is True
    assert result.passes_completed == 1
    assert result.stop_reason == "completed"
    assert result.credits_delta == 100


def test_rearms_until_pass_count_ceiling():
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        return _ok_result(delta=10)

    result = run_bounded_repeat(
        _Session(),
        object(),
        world_id="w",
        turns_left_fn=lambda: 50,
        caps=_Caps(),
        should_abort=lambda: False,
        is_armed=lambda: True,
        max_passes=3,
        run_chain_fn=fake_run,
    )
    assert calls["n"] == 3
    assert result.passes_completed == 3
    assert result.completed is True
    assert result.stop_reason == STOP_PASS_COUNT
    assert result.credits_delta == 30
    assert result.hops_completed == 6


def test_floor_halt_before_rearm():
    session = _Session(balance=5000)
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        # After first successful pass, drop balance to the floor.
        session._balance = 1000
        return _ok_result()

    caps = _Caps()
    result = run_bounded_repeat(
        session,
        object(),
        world_id="w",
        turns_left_fn=lambda: 50,
        caps=caps,
        should_abort=lambda: False,
        is_armed=lambda: True,
        max_passes=5,
        run_chain_fn=fake_run,
    )
    assert calls["n"] == 1
    assert result.passes_completed == 1
    assert result.completed is False
    assert result.stop_reason == HALT_FLOOR_REACHED


def test_profit_target_halt_before_rearm():
    session = _Session(balance=5000, profit=0)
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        session._profit = 2500
        return _ok_result()

    caps = _Caps()
    caps.profit_target = 2000
    result = run_bounded_repeat(
        session,
        object(),
        world_id="w",
        turns_left_fn=lambda: 50,
        caps=caps,
        should_abort=lambda: False,
        is_armed=lambda: True,
        max_passes=5,
        run_chain_fn=fake_run,
    )
    assert calls["n"] == 1
    assert result.passes_completed == 1
    assert result.stop_reason == HALT_PROFIT_TARGET_REACHED
    assert result.completed is False


def test_non_completed_pass_does_not_rearm():
    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1
        return _halt_result("turn_floor:0")

    result = run_bounded_repeat(
        _Session(),
        object(),
        world_id="w",
        turns_left_fn=lambda: 50,
        caps=_Caps(),
        should_abort=lambda: False,
        is_armed=lambda: True,
        max_passes=5,
        run_chain_fn=fake_run,
    )
    assert calls["n"] == 1
    assert result.passes_completed == 0
    assert result.stop_reason == "turn_floor:0"


def test_abort_and_disarm_halt():
    aborted = run_bounded_repeat(
        _Session(),
        object(),
        world_id="w",
        turns_left_fn=lambda: 50,
        caps=_Caps(),
        should_abort=lambda: True,
        is_armed=lambda: True,
        max_passes=3,
        run_chain_fn=lambda *a, **k: _ok_result(),
    )
    disarmed = run_bounded_repeat(
        _Session(),
        object(),
        world_id="w",
        turns_left_fn=lambda: 50,
        caps=_Caps(),
        should_abort=lambda: False,
        is_armed=lambda: False,
        max_passes=3,
        run_chain_fn=lambda *a, **k: _ok_result(),
    )
    assert aborted.stop_reason == "aborted"
    assert aborted.passes_completed == 0
    assert disarmed.stop_reason == "aborted"


def test_default_max_passes_is_ten():
    assert DEFAULT_MAX_PASSES == 10
