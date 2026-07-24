"""TW-04 TOCTOU / refuse-not-queue probes (WO-P2-025).

Axis 1 — acquire_driver / enter_auto_loop atomic mode+slot claim under one
lock hold (both directions) + a naive two-step sensitivity check.

Axis 2 — take_human fences an in-flight App driver; Session.send_raw holds
the human keystroke until release_driver (unit-level, no attach verb).

Attach-protocol e2e (AttachInputConn / fake_daemon attach) stays DEFER —
protocol.py has no attach verb yet. Do not invent attach here.
"""

import threading
import time

import pytest

from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.control_lock import (
    MODE_APP,
    MODE_HUMAN,
    ControlLock,
    ControlModeConflict,
)
from tw2002_aiclient.session.session import Session

from .conftest import FAKE_HOST, FAKE_PORT

_HOLD_S = 0.4
_POLL_MARGIN_S = 0.2


# ---------------------------------------------------------------------------
# Axis 1 -- atomic acquire_driver / enter_auto_loop
# ---------------------------------------------------------------------------


class _StretchedAcquireLock(ControlLock):
    """Real acquire_driver checks, stretched inside one lock hold."""

    def __init__(self, hold_s):
        super().__init__()
        self.hold_s = hold_s
        self.entered_hold = threading.Event()

    def acquire_driver(self):
        # Private fields under the SAME hold — do not call helpers that
        # re-acquire self._lock (deadlock).
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("controller_locked_by_human")
            if self._mode != MODE_APP:
                raise ControlModeConflict(f"controller_locked:{self._mode}")
            if self._auto_loop_held:
                raise ControlModeConflict("controller_locked_by_auto_loop")
            if self._driving:
                raise ControlModeConflict("controller_busy")
            self.entered_hold.set()
            time.sleep(self.hold_s)
            self._driving = True
            self._driver_fenced = False


class _StretchedEnterAutoLoopLock(ControlLock):
    """Reverse stretch: enter_auto_loop hold blocks concurrent acquire_driver."""

    def __init__(self, hold_s):
        super().__init__()
        self.hold_s = hold_s
        self.entered_hold = threading.Event()

    def enter_auto_loop(self):
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("locked_by_human_attach")
            if self._auto_loop_held:
                raise ControlModeConflict("already_running")
            if self._driving:
                raise ControlModeConflict("locked_by_active_driver")
            self.entered_hold.set()
            time.sleep(self.hold_s)
            self._mode = MODE_APP
            self._auto_loop_held = True


class _NaiveTwoStepAcquireLock(ControlLock):
    """Broken two-step acquire — sensitivity check for Axis 1 greens."""

    def __init__(self, hold_s):
        super().__init__()
        self.hold_s = hold_s
        self.entered_gap = threading.Event()

    def acquire_driver(self):
        with self._lock:
            mode = self._mode
            auto = self._auto_loop_held
        if mode == MODE_HUMAN:
            raise ControlModeConflict("controller_locked_by_human")
        if mode != MODE_APP:
            raise ControlModeConflict(f"controller_locked:{mode}")
        if auto:
            raise ControlModeConflict("controller_locked_by_auto_loop")
        self.entered_gap.set()
        time.sleep(self.hold_s)
        with self._lock:
            # Only re-checks _driving, never mode — historical bug shape.
            if self._driving:
                raise ControlModeConflict("controller_busy")
            self._driving = True
            self._driver_fenced = False


def test_real_acquire_driver_blocks_concurrent_take_human_for_the_full_hold():
    lock = _StretchedAcquireLock(_HOLD_S)
    driver_thread = threading.Thread(target=lock.acquire_driver)
    driver_thread.start()
    assert lock.entered_hold.wait(timeout=2.0), "acquire_driver() never entered its hold"

    result = {}

    def racer():
        try:
            lock.take_human()
            result["outcome"] = "took_human"
        except ControlModeConflict as e:
            result["outcome"] = str(e)

    racer_thread = threading.Thread(target=racer)
    racer_thread.start()

    time.sleep(_POLL_MARGIN_S)
    assert "outcome" not in result, (
        "take_human() returned WHILE acquire_driver() still held the lock -- TOCTOU"
    )

    driver_thread.join(timeout=2.0)
    racer_thread.join(timeout=2.0)
    assert result["outcome"] == "took_human"
    assert lock.is_driving() is True
    assert lock.is_driver_fenced() is True
    assert lock.mode == MODE_HUMAN


def test_real_enter_auto_loop_blocks_concurrent_acquire_driver_for_the_full_hold():
    lock = _StretchedEnterAutoLoopLock(_HOLD_S)
    driver_thread = threading.Thread(target=lock.enter_auto_loop)
    driver_thread.start()
    assert lock.entered_hold.wait(timeout=2.0), "enter_auto_loop() never entered its hold"

    result = {}

    def racer():
        try:
            lock.acquire_driver()
            result["outcome"] = "acquired"
        except ControlModeConflict as e:
            result["outcome"] = str(e)

    racer_thread = threading.Thread(target=racer)
    racer_thread.start()

    time.sleep(_POLL_MARGIN_S)
    assert "outcome" not in result, (
        "acquire_driver() returned WHILE enter_auto_loop() still held the lock -- TOCTOU"
    )

    driver_thread.join(timeout=2.0)
    racer_thread.join(timeout=2.0)
    assert result["outcome"] == "controller_locked_by_auto_loop"
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is True
    assert lock.is_driving() is False


def test_naive_two_step_acquire_driver_lets_take_human_interleave_mid_gap():
    lock = _NaiveTwoStepAcquireLock(_HOLD_S)
    driver_thread = threading.Thread(target=lock.acquire_driver)
    driver_thread.start()
    assert lock.entered_gap.wait(timeout=2.0), "naive acquire_driver() never entered its gap"

    result = {}

    def racer():
        try:
            lock.take_human()
            result["outcome"] = "took_human"
        except ControlModeConflict as e:
            result["outcome"] = str(e)

    racer_thread = threading.Thread(target=racer)
    racer_thread.start()
    racer_thread.join(timeout=2.0)

    assert result["outcome"] == "took_human"
    assert lock.mode == MODE_HUMAN

    driver_thread.join(timeout=2.0)
    # Naive acquire claims the slot anyway — two-writer sensitivity proof.
    assert lock.is_driving() is True


def test_acquire_driver_refuses_not_queues_when_busy():
    lock = ControlLock()
    lock.acquire_driver()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.acquire_driver()
    assert str(exc_info.value) == "controller_busy"


def test_acquire_driver_refuses_not_queues_when_human_holds():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.acquire_driver()
    assert str(exc_info.value) == "controller_locked_by_human"


# ---------------------------------------------------------------------------
# Axis 2 -- fence + send_raw courtesy wait (no attach verb)
# ---------------------------------------------------------------------------


def test_take_human_fences_in_flight_driver_without_refusing():
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()  # must not raise
    assert lock.mode == MODE_HUMAN
    assert lock.is_driving() is True
    assert lock.is_driver_fenced() is True


def test_send_raw_waits_for_fenced_driver_then_sends(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(
        TelnetConnection, "send_bytes", lambda self, data, secret=False: sent.append(data)
    )
    session = Session(FAKE_HOST, FAKE_PORT, "test", str(tmp_path))
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()
    assert lock.is_driver_fenced() is True

    result = {}

    def send_call():
        session.send_raw(b"H", control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.2)

    assert "done" not in result
    assert sent == []

    lock.release_driver()
    t.join(timeout=2.0)

    assert result.get("done") is True
    assert sent == [b"H"]
    assert session.last_sender == "human"


# ---------------------------------------------------------------------------
# Axis 2 attach e2e — DEFER
# ---------------------------------------------------------------------------
# Archive proved attach connect + keystroke fence via AttachInputConn against
# fake_daemon. Live protocol.py only dispatches ensure/status/screen/stop;
# attach returns unknown_verb. Re-open with test_attach_protocol when attach
# lands — do not invent the verb here.
