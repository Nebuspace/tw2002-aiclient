import threading

import pytest

from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session import stardock_hold
from tw2002_aiclient.stardock_hold_driver import HoldRunResult
from tw2002_aiclient.stardock_hold_plan import plan_from_evidence


class _Session:
    pass


def _plan():
    return plan_from_evidence(
        "world-a",
        stardock_sector=751,
        empty_holds=20,
        hold_price=1468,
        credits=50_000,
        qty=2,
    )


def test_start_refuses_stale_fingerprint_before_lock_or_thread():
    plan = _plan()
    lock = ControlLock()
    runner = stardock_hold.StardockHoldRunner(_Session(), lock)

    with pytest.raises(stardock_hold.StardockHoldRefused, match="hold_identity_stale"):
        runner.start(
            plan.world_id,
            "not-the-plan-fingerprint",
            stardock_sector=plan.stardock_sector,
            empty_holds=plan.empty_holds,
            hold_price=plan.hold_price,
            credits=plan.credits,
            qty=plan.qty,
        )

    assert runner.snapshot().running is False
    assert lock.is_auto_loop_held() is False


def test_start_refuses_invalid_plan_before_lock():
    lock = ControlLock()
    runner = stardock_hold.StardockHoldRunner(_Session(), lock)

    with pytest.raises(stardock_hold.StardockHoldRefused, match="hold_plan_invalid"):
        runner.start(
            "world-a",
            "deadbeef",
            stardock_sector=0,
            empty_holds=20,
            hold_price=1468,
            credits=50_000,
            qty=1,
        )

    assert runner.snapshot().running is False
    assert lock.is_auto_loop_held() is False


def test_exact_start_runs_once_and_stop_reaches_abort_predicate(monkeypatch):
    plan = _plan()
    entered = threading.Event()

    def _run(_session, resolved, **kwargs):
        assert resolved == plan
        entered.set()
        assert kwargs["is_armed"]() is True
        assert kwargs["should_abort"]() is False
        while not kwargs["should_abort"]():
            threading.Event().wait(0.005)
        return HoldRunResult(False, "halted", "aborted", 0)

    monkeypatch.setattr(stardock_hold, "run_hold_purchase", _run)
    lock = ControlLock()
    runner = stardock_hold.StardockHoldRunner(_Session(), lock)

    snapshot = runner.start(
        plan.world_id,
        plan.fingerprint,
        stardock_sector=plan.stardock_sector,
        empty_holds=plan.empty_holds,
        hold_price=plan.hold_price,
        credits=plan.credits,
        qty=plan.qty,
        cash_floor=2_000,
    )
    assert entered.wait(1.0)
    assert snapshot.running is True
    assert lock.is_auto_loop_held() is True

    stopped = runner.stop(join_timeout=1.0)

    assert stopped.running is False
    assert stopped.report.outcome == "halted"
    assert stopped.report.reason == "aborted"
    assert lock.is_auto_loop_held() is False
