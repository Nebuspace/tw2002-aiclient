"""ControlLock (tw2002_aiclient.session.control_lock) — pure unit tests.

Greenfield rewrite of the archive suite: modes are exactly
{app, human, spectate}; auto_loop collapses to app.
"""

import pytest

from tw2002_aiclient.session.control_lock import (
    MODE_APP,
    MODE_HUMAN,
    MODE_SPECTATE,
    ControlLock,
    ControlModeConflict,
)


def test_app_may_send_by_default():
    lock = ControlLock()
    assert lock.mode == MODE_APP
    assert lock.app_may_send() is True
    assert lock.is_auto_loop_held() is False


def test_exposed_modes_are_exactly_app_human_spectate():
    lock = ControlLock()
    seen = {lock.mode}
    lock.set_mode(MODE_SPECTATE)
    seen.add(lock.mode)
    lock.set_mode(MODE_APP)
    lock.take_human()
    seen.add(lock.mode)
    assert seen == {MODE_APP, MODE_HUMAN, MODE_SPECTATE}
    assert "auto_loop" not in seen


def test_take_human_blocks_app():
    lock = ControlLock()
    lock.take_human()
    assert lock.mode == MODE_HUMAN
    assert lock.app_may_send() is False


def test_take_human_twice_raises():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.take_human()
    assert str(exc_info.value) == "already_attached"


def test_release_human_returns_to_app():
    lock = ControlLock()
    lock.take_human()
    lock.release_human()
    assert lock.mode == MODE_APP
    assert lock.app_may_send() is True


def test_release_human_is_safe_when_not_held():
    lock = ControlLock()
    lock.release_human()
    assert lock.mode == MODE_APP


def test_take_human_again_after_release_succeeds():
    lock = ControlLock()
    lock.take_human()
    lock.release_human()
    lock.take_human()
    assert lock.mode == MODE_HUMAN


# -- set_mode() ----------------------------------------------------------

def test_set_mode_switches_between_settable_modes():
    lock = ControlLock()
    lock.set_mode(MODE_SPECTATE)
    assert lock.mode == MODE_SPECTATE
    assert lock.app_may_send() is False

    lock.set_mode(MODE_APP)
    assert lock.mode == MODE_APP
    assert lock.app_may_send() is True


def test_set_mode_rejects_unknown_mode_name():
    lock = ControlLock()
    with pytest.raises(ValueError):
        lock.set_mode("warp_speed")


def test_set_mode_rejects_auto_loop_alias():
    # auto_loop collapses to app — not a settable mode string.
    lock = ControlLock()
    with pytest.raises(ValueError):
        lock.set_mode("auto_loop")


def test_set_mode_cannot_enter_human_mode():
    lock = ControlLock()
    with pytest.raises(ValueError):
        lock.set_mode(MODE_HUMAN)


def test_set_mode_cannot_clobber_an_active_human_attach():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.set_mode(MODE_SPECTATE)
    assert str(exc_info.value) == "locked_by_human_attach"
    assert lock.mode == MODE_HUMAN


def test_set_mode_cannot_clobber_a_running_auto_loop():
    lock = ControlLock()
    lock.enter_auto_loop()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.set_mode(MODE_SPECTATE)
    assert str(exc_info.value) == "locked_by_auto_loop"
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is True


# -- enter_auto_loop() / leave_auto_loop() — collapses to app ------------

def test_enter_auto_loop_collapses_to_app():
    lock = ControlLock()
    lock.enter_auto_loop()
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is True
    assert lock.app_may_send() is True


def test_enter_auto_loop_twice_raises():
    lock = ControlLock()
    lock.enter_auto_loop()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.enter_auto_loop()
    assert str(exc_info.value) == "already_running"


def test_enter_auto_loop_refuses_to_preempt_an_active_attach():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.enter_auto_loop()
    assert str(exc_info.value) == "locked_by_human_attach"
    assert lock.mode == MODE_HUMAN


def test_take_human_always_wins_over_auto_loop():
    # Canon: human claim is unconditional — App (incl. auto_loop hold) cannot refuse.
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.take_human()
    assert lock.mode == MODE_HUMAN
    assert lock.is_auto_loop_held() is False


def test_leave_auto_loop_clears_hold_keeps_app():
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is False
    assert lock.app_may_send() is True


def test_leave_auto_loop_is_safe_when_not_held():
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()
    lock.take_human()
    lock.leave_auto_loop()  # stale — must not touch MODE_HUMAN
    assert lock.mode == MODE_HUMAN


def test_enter_auto_loop_again_after_leave_succeeds():
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()
    lock.enter_auto_loop()
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is True


# -- acquire_driver() / release_driver() / is_driving() ------------------

def test_is_driving_false_by_default():
    lock = ControlLock()
    assert lock.is_driving() is False


def test_acquire_driver_marks_is_driving_true():
    lock = ControlLock()
    lock.acquire_driver()
    assert lock.is_driving() is True
    assert lock.mode == MODE_APP


def test_acquire_driver_twice_raises_controller_busy():
    lock = ControlLock()
    lock.acquire_driver()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.acquire_driver()
    assert str(exc_info.value) == "controller_busy"
    assert lock.is_driving() is True


def test_release_driver_clears_is_driving():
    lock = ControlLock()
    lock.acquire_driver()
    lock.release_driver()
    assert lock.is_driving() is False


def test_release_driver_is_safe_when_not_held():
    lock = ControlLock()
    lock.release_driver()
    assert lock.is_driving() is False


def test_acquire_driver_again_after_release_succeeds():
    lock = ControlLock()
    lock.acquire_driver()
    lock.release_driver()
    lock.acquire_driver()
    assert lock.is_driving() is True


def test_enter_auto_loop_refuses_to_preempt_an_active_driver():
    lock = ControlLock()
    lock.acquire_driver()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.enter_auto_loop()
    assert str(exc_info.value) == "locked_by_active_driver"
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is False

    lock.release_driver()
    lock.enter_auto_loop()
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is True


def test_acquire_driver_refuses_when_auto_loop_holds():
    lock = ControlLock()
    lock.enter_auto_loop()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.acquire_driver()
    assert str(exc_info.value) == "controller_locked_by_auto_loop"
    assert lock.is_driving() is False


def test_acquire_driver_refuses_when_human_attach_holds():
    lock = ControlLock()
    lock.take_human()
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.acquire_driver()
    assert str(exc_info.value) == "controller_locked_by_human"
    assert lock.is_driving() is False


def test_acquire_driver_refuses_in_spectate():
    lock = ControlLock()
    lock.set_mode(MODE_SPECTATE)
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.acquire_driver()
    assert str(exc_info.value) == "spectate_read_only"
    assert lock.is_driving() is False


# -- WO-CLEANPREEMPT: fence courtesy ------------------------------------

def test_take_human_never_refuses_while_driving():
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()
    assert lock.mode == MODE_HUMAN
    assert lock.is_driving() is True
    assert lock.is_driver_fenced() is True


def test_is_driver_fenced_false_by_default():
    lock = ControlLock()
    assert lock.is_driver_fenced() is False


def test_take_human_does_not_fence_when_nothing_is_driving():
    lock = ControlLock()
    lock.take_human()
    assert lock.is_driver_fenced() is False


def test_release_driver_clears_the_fence():
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()
    assert lock.is_driver_fenced() is True
    lock.release_driver()
    assert lock.is_driver_fenced() is False
    assert lock.is_driving() is False


def test_fresh_acquire_driver_after_a_fenced_release_starts_unfenced():
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()
    lock.release_driver()
    lock.release_human()
    lock.acquire_driver()
    assert lock.is_driver_fenced() is False


def test_driver_lock_never_leaks_after_a_dispatch_ends():
    lock = ControlLock()
    lock.acquire_driver()
    lock.release_driver()
    assert lock.is_driving() is False
    lock.take_human()
    assert lock.mode == MODE_HUMAN
    lock.release_human()
    lock.enter_auto_loop()
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is True


def test_no_legacy_drive_mode_symbols_exported():
    import tw2002_aiclient.session.control_lock as mod

    assert not hasattr(mod, "MODE_AUTO_LOOP")
    assert getattr(mod, "MODE_APP") == "app"
    assert {MODE_APP, MODE_HUMAN, MODE_SPECTATE} == {"app", "human", "spectate"}
