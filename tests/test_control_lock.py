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
    token = lock.enter_auto_loop()
    lock.leave_auto_loop(token)
    assert lock.mode == MODE_APP
    assert lock.is_auto_loop_held() is False
    assert lock.app_may_send() is True


def test_leave_auto_loop_is_safe_when_not_held():
    lock = ControlLock()
    token = lock.enter_auto_loop()
    lock.leave_auto_loop(token)
    lock.take_human()
    lock.leave_auto_loop(token)  # stale (already released) — must not touch MODE_HUMAN
    assert lock.mode == MODE_HUMAN


def test_enter_auto_loop_again_after_leave_succeeds():
    lock = ControlLock()
    token = lock.enter_auto_loop()
    lock.leave_auto_loop(token)
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


# -- WO-CONTROL-LOCK-AUTOLOOP-FENCE: the same courtesy for an auto_loop
# hold, not just a dispatch. Mirrors the WO-CLEANPREEMPT block above,
# one predicate per source, so a regression in either fence path fails
# its own dedicated test rather than a shared one.

def test_take_human_never_refuses_while_auto_loop_held():
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.take_human()
    assert lock.mode == MODE_HUMAN
    assert lock.is_auto_loop_held() is False  # revoked...
    assert lock.is_driver_fenced() is True  # ...but FENCED, not merely revoked


def test_take_human_does_not_fence_the_auto_loop_flag_when_nothing_is_held():
    lock = ControlLock()
    lock.take_human()
    assert lock.is_driver_fenced() is False


def test_leave_auto_loop_clears_the_fence_it_raised():
    lock = ControlLock()
    token = lock.enter_auto_loop()
    lock.take_human()
    assert lock.is_driver_fenced() is True
    lock.leave_auto_loop(token)
    assert lock.is_driver_fenced() is False


def test_leave_auto_loop_with_no_prior_fence_is_a_no_op():
    """No token, no prior `enter_auto_loop()` at all -- the default
    (`generation=None`) must never accidentally match `_auto_loop_
    generation`'s starting value and release something that was never
    entered."""
    lock = ControlLock()
    lock.leave_auto_loop()
    assert lock.is_driver_fenced() is False


def test_leave_auto_loop_with_no_token_does_not_release_a_live_hold():
    """The same default, but with something genuinely held: a caller that
    forgot its token (or never had one) must not release ANY hold just
    because one happens to be standing -- the generation match is the
    only thing that may authorize a release, never "something is held
    and nothing else was specified"."""
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()  # no token supplied
    assert lock.is_auto_loop_held() is True


def test_leave_auto_loop_with_a_wrong_token_does_not_release_the_hold():
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop(999999)  # never a token this lock minted
    assert lock.is_auto_loop_held() is True


def test_fresh_enter_auto_loop_after_a_fenced_leave_starts_unfenced():
    """Cipher's LOW, closed correctly: a fresh generation comes up
    unfenced BY CONSTRUCTION whenever its immediate predecessor released
    CLEANLY first (that release, matching its own generation, already
    cleared the flag) -- never because `enter_auto_loop()` itself resets
    anything. See the next test for the case where the predecessor has
    NOT released -- the fence must NOT be cleared there."""
    lock = ControlLock()
    token = lock.enter_auto_loop()
    lock.take_human()
    lock.leave_auto_loop(token)
    lock.release_human()
    lock.enter_auto_loop()
    assert lock.is_driver_fenced() is False


def test_enter_auto_loop_does_not_erase_a_still_unreleased_predecessors_fence():
    """The trap the hub warned against, pinned directly: a tempting
    "generation token" implementation is *newest wins* -- a fresh
    `enter_auto_loop()` reaches back and clears whatever the previous
    generation left standing, including its fence. That is wrong: the
    predecessor might still be genuinely mid-send on the one shared wire
    (the wedged-send hazard, tracked separately as
    WO-WEDGED-SEND-FENCE-STICKS and NOT something this fix may downgrade
    in either direction). So a fence from a generation that has not yet
    released must survive a fresh `enter_auto_loop()` untouched."""
    lock = ControlLock()
    token_a = lock.enter_auto_loop()
    lock.take_human()
    lock.release_human()
    # A's own release never arrives here -- standing in for "wedged".
    token_b = lock.enter_auto_loop()
    assert token_b != token_a
    assert lock.is_driver_fenced() is True, (
        "a fresh generation must not silently erase a still-outstanding "
        "predecessor's fence -- that would reopen the exact TOCTOU this "
        "WO exists to close, via the new generation instead of the old one"
    )


def test_leave_auto_loop_does_not_clear_an_unrelated_dispatch_fence():
    """The two fences are independent flags with independent release
    paths on purpose -- a `leave_auto_loop()` with nothing of its own to
    release must never clear the OTHER fence, or a stray call could let a
    human byte through early while a genuinely fenced dispatch is still
    winding down."""
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()
    assert lock.is_driver_fenced() is True
    lock.leave_auto_loop()  # nothing entered here -- must not touch it
    assert lock.is_driver_fenced() is True
    lock.release_driver()
    assert lock.is_driver_fenced() is False


def test_release_driver_does_not_clear_an_unrelated_auto_loop_fence():
    """The mirror of the test above: a `release_driver()` with nothing of
    its own to release must never clear a fence `take_human()` raised on
    an auto_loop hold."""
    lock = ControlLock()
    token = lock.enter_auto_loop()
    lock.take_human()
    assert lock.is_driver_fenced() is True
    lock.release_driver()  # nothing driving here -- must not touch it
    assert lock.is_driver_fenced() is True
    lock.leave_auto_loop(token)
    assert lock.is_driver_fenced() is False


# -- Mack's CRITICAL, reproduced verbatim against the real class ---------
#
# A stale release, arriving after a human detached and a FRESH generation
# has already taken the hold, must have NO observable effect on that new
# generation -- neither its hold nor its fence. Before the generation
# token, `leave_auto_loop()` was unconditional: A enters, a human preempts
# and detaches, B enters fresh, and A's own stale release (e.g. a wedged
# run's `finally` finally waking up) destroyed B's hold -- and a THIRD
# `enter_auto_loop()` then wrongly SUCCEEDED. Two drivers on one wire.


def test_a_stale_leave_from_a_superseded_generation_cannot_touch_the_new_hold():
    lock = ControlLock()
    token_a = lock.enter_auto_loop()
    lock.take_human()      # preempts A -- held cleared, A's fence raised
    lock.release_human()   # human detaches
    token_b = lock.enter_auto_loop()  # B enters fresh
    assert token_b != token_a

    lock.leave_auto_loop(token_a)  # A's STALE release, arriving late

    assert lock.is_auto_loop_held() is True, "A's stale release must not touch B's hold"
    with pytest.raises(ControlModeConflict) as exc_info:
        lock.enter_auto_loop()  # C attempts to enter while B still runs
    assert str(exc_info.value) == "already_running"


def test_a_stale_leave_cannot_clear_a_newer_generations_genuine_fence():
    """The fence-race variant Mack named as worse: B is ALSO preempted
    (its own fence correctly raised) before A's stale release arrives. A's
    stale call must not clear B's fence -- that would let a human byte
    race B's in-flight step, reopening the exact TOCTOU this WO exists to
    close, via an unrelated stale caller."""
    lock = ControlLock()
    token_a = lock.enter_auto_loop()
    lock.take_human()
    lock.release_human()
    lock.enter_auto_loop()  # B enters fresh
    lock.take_human()       # B preempted too -- its own fence raised
    assert lock.is_driver_fenced() is True

    lock.leave_auto_loop(token_a)  # A's STALE release, arriving even later

    assert lock.is_driver_fenced() is True, "A's stale release must not clear B's genuine fence"


# -- Round 3: the CRITICAL relocated to the sibling flag -----------------
#
# Both reviewers independently found the same gap in the round-2 fix, and
# it is the round-2 reasoning not applied a second time. `leave_auto_loop`'s
# generation gate asked "am I current?" -- correct for the HOLD -- but
# used that SAME question to decide whether to clear the FENCE, which is
# not scoped to who is current, only to who RAISED it. A generation can
# be current for its own hold while being a total stranger to a fence it
# merely inherited (by design -- see `enter_auto_loop`'s own docstring).
# All 112 tests from round 2 passed with this hole present: none of them
# constructed "B inherits a fence it never raised, then B alone releases."
#
# Round 3's OWN fix (a single "owner" generation slot) was itself
# superseded by round 4's set (see below) -- a second, independently
# preempted generation had nowhere to go but overwrite that one slot.
# The two tests below still pin exactly the property round 3 established
# (a non-owning release must not erase someone else's claim); they pass
# unchanged under the set, which is a strict generalization -- a set of
# size one behaves exactly like the single owner slot did.


def test_a_generations_clean_release_does_not_erase_an_inherited_fence_it_never_raised():
    """The primary repro, reproduced verbatim against the real class
    (Mack CRITICAL / Cipher MEDIUM, round 3). B inherits A's fence by
    design (the round-2 fix: a fresh generation must not erase a
    still-outstanding predecessor's fence). But B itself was never
    preempted -- and B's own ORDINARY, CLEAN release, gated only on "is B
    current" (true), must not be the thing that erases a fence B never
    raised. A's fence, and whatever A might still be doing on the wire,
    survives an event that has nothing to do with A."""
    lock = ControlLock()
    token_a = lock.enter_auto_loop()
    lock.take_human()          # preempts A -- fences A specifically
    lock.release_human()
    token_b = lock.enter_auto_loop()  # B inherits A's fence, correctly
    assert lock.is_driver_fenced() is True

    lock.leave_auto_loop(token_b)  # B's OWN clean release -- B was never fenced

    assert lock.is_auto_loop_held() is False, "B's own hold still releases normally"
    assert lock.is_driver_fenced() is True, (
        "B's clean release must not erase A's fence -- B never raised it"
    )


def test_the_fences_rightful_owner_can_still_release_it_after_a_newer_generations_clean_exit():
    """The mirror Cipher named: the fence is not permanently stuck once
    its owner is no longer the current generation. Continuing directly
    from the test above -- after B's clean exit leaves A's fence standing
    -- A's own release (stale for the HOLD, which B now owns; but still
    the rightful owner of the FENCE) must still be able to clear it. The
    fence's gate is "did `generation` raise it", never "is `generation`
    current", and the two are independent in both directions."""
    lock = ControlLock()
    token_a = lock.enter_auto_loop()
    lock.take_human()
    lock.release_human()
    token_b = lock.enter_auto_loop()
    lock.leave_auto_loop(token_b)  # B's clean release -- does not touch A's fence
    assert lock.is_driver_fenced() is True

    lock.leave_auto_loop(token_a)  # A's own release, arriving late

    assert lock.is_driver_fenced() is False, "A may still release the fence it actually raised"


# -- Round 4: a single owner slot is the SAME defect at a different ------
# cardinality -- the fence is a SET of outstanding generations, not a
# bool-plus-one-owner-slot. Cipher's finding: a SECOND preemption (a
# different generation, ALSO fenced before the first released) had
# nowhere to go but overwrite the round-3 owner slot, silently erasing
# the first generation's claim -- not merely making it unreachable, but
# gone. Trace, reproduced verbatim:
#
#   A enters, preempted, wedged        -> fenced True  (owner slot: A)
#   B enters, ALSO preempted, wedged   -> fenced True  (owner slot: B -- A's stamp overwritten)
#   B releases its own claim           -> fenced FALSE  <- A still wedged, claim lost


def test_two_concurrently_fenced_generations_each_release_independently():
    """The set closes this by construction: A and B are both members
    after both are preempted, and releasing one discards only that one --
    the other's claim is untouched no matter which releases first."""
    lock = ControlLock()
    token_a = lock.enter_auto_loop()
    lock.take_human()          # preempts A -- A's claim is now outstanding
    lock.release_human()
    token_b = lock.enter_auto_loop()
    lock.take_human()          # preempts B too -- BOTH claims now outstanding
    lock.release_human()
    assert lock.is_driver_fenced() is True

    lock.leave_auto_loop(token_b)  # B releases its OWN claim only

    assert lock.is_driver_fenced() is True, (
        "A's claim must survive B's independent release -- a single owner "
        "slot would have been overwritten by B's preemption and erased "
        "here, exactly the round-4 defect"
    )

    lock.leave_auto_loop(token_a)  # A finally releases too

    assert lock.is_driver_fenced() is False


def test_no_legacy_drive_mode_symbols_exported():
    import tw2002_aiclient.session.control_lock as mod

    assert not hasattr(mod, "MODE_AUTO_LOOP")
    assert getattr(mod, "MODE_APP") == "app"
    assert {MODE_APP, MODE_HUMAN, MODE_SPECTATE} == {"app", "human", "spectate"}
