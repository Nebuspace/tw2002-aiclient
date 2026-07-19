"""ControlLock (twclient/control_lock.py) — pure unit tests, no sockets,
no threads started. See test_attach_protocol.py for the real-socket
end-to-end handoff proof."""

import pytest

from twclient.control_lock import (
    MODE_AI_PILOT,
    MODE_AUTO_LOOP,
    MODE_HUMAN,
    MODE_SPECTATE,
    ControlLock,
    ControlModeConflict,
)


def test_ai_may_send_by_default():
    lock = ControlLock()
    assert lock.mode == MODE_AI_PILOT
    assert lock.ai_may_send() is True


def test_take_human_blocks_ai():
    lock = ControlLock()
    lock.take_human()
    assert lock.mode == MODE_HUMAN
    assert lock.ai_may_send() is False


def test_take_human_twice_raises():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict):
        lock.take_human()


def test_release_human_returns_to_ai_pilot():
    lock = ControlLock()
    lock.take_human()
    lock.release_human()
    assert lock.mode == MODE_AI_PILOT
    assert lock.ai_may_send() is True


def test_release_human_is_safe_when_not_held():
    lock = ControlLock()
    lock.release_human()  # must not raise
    assert lock.mode == MODE_AI_PILOT


def test_take_human_again_after_release_succeeds():
    lock = ControlLock()
    lock.take_human()
    lock.release_human()
    lock.take_human()  # must not raise -- a fresh attach after a clean detach
    assert lock.mode == MODE_HUMAN


# -- set_mode() -- the future control panel's non-exclusive seam --------

def test_set_mode_switches_between_settable_modes():
    lock = ControlLock()
    lock.set_mode(MODE_SPECTATE)
    assert lock.mode == MODE_SPECTATE
    assert lock.ai_may_send() is False  # paused, not just "not human"

    lock.set_mode(MODE_AI_PILOT)
    assert lock.mode == MODE_AI_PILOT
    assert lock.ai_may_send() is True


def test_set_mode_rejects_unknown_mode_name():
    lock = ControlLock()
    with pytest.raises(ValueError):
        lock.set_mode("warp_speed")


def test_set_mode_rejects_auto_loop_even_though_it_is_now_a_real_mode():
    # MODE_AUTO_LOOP is a real, wired mode (see enter_auto_loop() below)
    # but deliberately NOT set_mode()-settable -- only LoopPlayer.start()
    # may enter it, so "auto_loop" is on without an actually-running
    # player thread never happens. Must raise cleanly either way.
    lock = ControlLock()
    with pytest.raises(ValueError):
        lock.set_mode(MODE_AUTO_LOOP)


def test_set_mode_cannot_enter_human_mode():
    # MODE_HUMAN is exclusive/connection-scoped -- only take_human() can
    # enter it, never a plain set_mode() call.
    lock = ControlLock()
    with pytest.raises(ValueError):
        lock.set_mode(MODE_HUMAN)


def test_set_mode_cannot_clobber_an_active_human_attach():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict):
        lock.set_mode(MODE_SPECTATE)
    assert lock.mode == MODE_HUMAN  # unchanged by the rejected attempt


def test_set_mode_cannot_clobber_a_running_auto_loop():
    lock = ControlLock()
    lock.enter_auto_loop()
    with pytest.raises(ControlModeConflict):
        lock.set_mode(MODE_SPECTATE)
    assert lock.mode == MODE_AUTO_LOOP


# -- enter_auto_loop()/leave_auto_loop() -- LoopPlayer's exclusive seam --

def test_enter_auto_loop_blocks_ai_and_is_observable():
    lock = ControlLock()
    lock.enter_auto_loop()
    assert lock.mode == MODE_AUTO_LOOP
    assert lock.ai_may_send() is False


def test_enter_auto_loop_twice_raises():
    lock = ControlLock()
    lock.enter_auto_loop()
    with pytest.raises(ControlModeConflict):
        lock.enter_auto_loop()


def test_enter_auto_loop_refuses_to_preempt_an_active_attach():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict):
        lock.enter_auto_loop()
    assert lock.mode == MODE_HUMAN


def test_take_human_refuses_to_preempt_a_running_auto_loop():
    lock = ControlLock()
    lock.enter_auto_loop()
    with pytest.raises(ControlModeConflict):
        lock.take_human()
    assert lock.mode == MODE_AUTO_LOOP


def test_leave_auto_loop_returns_to_ai_pilot():
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()
    assert lock.mode == MODE_AI_PILOT
    assert lock.ai_may_send() is True


def test_leave_auto_loop_is_safe_when_not_the_current_mode():
    # A stale/duplicate call from a finishing player thread must never
    # clobber a DIFFERENT mode set legitimately in the meantime.
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()
    lock.take_human()
    lock.leave_auto_loop()  # stale call -- must not touch MODE_HUMAN
    assert lock.mode == MODE_HUMAN


def test_enter_auto_loop_again_after_leave_succeeds():
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()
    lock.enter_auto_loop()  # must not raise
    assert lock.mode == MODE_AUTO_LOOP


# -- acquire_driver()/release_driver()/is_driving() -- TW-04's exclusive
# active-driver slot: at most one do/send-family dispatch mid-flight -----

def test_is_driving_false_by_default():
    lock = ControlLock()
    assert lock.is_driving() is False


def test_acquire_driver_marks_is_driving_true():
    lock = ControlLock()
    lock.acquire_driver()
    assert lock.is_driving() is True
    assert lock.mode == MODE_AI_PILOT  # orthogonal to mode -- still ai_pilot


def test_acquire_driver_twice_raises_controller_busy():
    lock = ControlLock()
    lock.acquire_driver()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.acquire_driver()
    assert str(exc_info.value) == "controller_busy"
    assert lock.is_driving() is True  # unchanged by the rejected attempt


def test_release_driver_clears_is_driving():
    lock = ControlLock()
    lock.acquire_driver()
    lock.release_driver()
    assert lock.is_driving() is False


def test_release_driver_is_safe_when_not_held():
    lock = ControlLock()
    lock.release_driver()  # must not raise
    assert lock.is_driving() is False


def test_acquire_driver_again_after_release_succeeds():
    lock = ControlLock()
    lock.acquire_driver()
    lock.release_driver()
    lock.acquire_driver()  # must not raise
    assert lock.is_driving() is True


# -- TW-04's second incident: enter_auto_loop() must not preempt an
# actively-driving ai_pilot dispatch -------------------------------------

def test_enter_auto_loop_refuses_to_preempt_an_active_driver():
    lock = ControlLock()
    lock.acquire_driver()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.enter_auto_loop()
    assert str(exc_info.value) == "locked_by_active_driver"
    assert lock.mode == MODE_AI_PILOT  # never transitioned

    lock.release_driver()
    lock.enter_auto_loop()  # succeeds once the driver releases
    assert lock.mode == MODE_AUTO_LOOP


def test_driver_lock_never_leaks_after_a_dispatch_ends():
    # Mode-transition/release proof: once a driver releases (mirroring a
    # completed dispatch), BOTH the driver slot AND the mode machine are
    # free again -- a stuck/leaked flag would wedge either take_human()
    # or enter_auto_loop() forever.
    lock = ControlLock()
    lock.acquire_driver()
    lock.release_driver()
    assert lock.is_driving() is False
    lock.take_human()  # must not raise -- nothing left held
    assert lock.mode == MODE_HUMAN
    lock.release_human()
    lock.enter_auto_loop()  # must not raise either
    assert lock.mode == MODE_AUTO_LOOP
