"""TW-04 TOCTOU adversarial probes (Mack — behavioral QA) -- offline
concurrency tests driving control_lock.ControlLock and
protocol._driving_dispatch directly, plus one end-to-end pass through
the real fake_daemon fixture (real ThreadingUnixServer/CommandHandler,
unmodified). No daemon spawn against the live game, no network -- this
file never touches run/twd.sock.

Axis 1 -- is acquire_driver()'s mode+driver-slot claim genuinely atomic
against a concurrent enter_auto_loop()/take_human(), in BOTH directions?
Proven three ways below:
  1. The REAL (unmodified) acquire_driver() logic, artificially
     stretched to hold `self._lock` open longer, blocks a concurrent
     take_human() racer for the FULL hold -- no early return, no
     mid-window interleave.
  2. The reverse direction: the REAL enter_auto_loop() logic, same
     stretch, blocks a concurrent acquire_driver() racer the same way.
  3. A deliberately NON-atomic two-step variant -- reproducing the
     EXACT pre-P0-fix shape acquire_driver()'s own docstring describes
     (mode check and driver-slot claim as two SEPARATE lock
     acquisitions) -- lets the SAME racer interleave mid-window,
     landing both MODE_HUMAN and is_driving()==True at once. This is
     the sensitivity check: it proves tests 1/2 aren't just "green
     because nothing was tried" -- the exact same technique catches a
     real violation when one exists.

Axis 2 -- take_human() checks ONLY `self._mode`, never `self._driving`,
unlike enter_auto_loop() (which explicitly raises
`ControlModeConflict("locked_by_active_driver")` while a driver is
mid-flight -- see control_lock.py). This WAS a real, reachable gap
(mack's original finding, see the module-bottom verdict comment for the
full pre-fix analysis): a `tw attach` connecting while a `do` dispatch
was deliberately held mid-`wait_settle()` succeeded anyway, and a raw
keystroke reached `session.send_raw()` -- gated on nothing but the
byte-level send_lock -- WHILE the ai_pilot dispatch's own send-then-
settle window was still open, corrupting the eventual ledger entry's
action->outcome mapping.

WO-CLEANPREEMPT fixed this: take_human() still succeeds instantly (the
human still always wins immediately -- see its own docstring), but a
dispatch caught mid-flight is now FENCED
(control_lock.ControlLock.is_driver_fenced()) instead of silently
ignored. `session.send_raw()` holds the human's own keystroke off the
wire until the fenced dispatch actually releases (a bounded wait), and
the fenced dispatch's own ledger entry is flagged
`interrupted_by_human=True` (protocol.py's `_driver_was_fenced()` /
ledger.py's additive field) so a pattern-learning consumer can exclude
it. Proven end-to-end below, assertions flipped from the original
finding.
"""

import threading
import time

from twclient.control_lock import (
    MODE_AI_PILOT,
    MODE_AUTO_LOOP,
    MODE_HUMAN,
    ControlLock,
    ControlModeConflict,
)
from twclient.interactive_app import AttachInputConn

from .conftest import send_request

# Real-thread wall-clock margins, matching this codebase's own established
# convention in test_active_driver.py (0.2s settle margin against a 2.0s
# blocking-thread timeout) rather than inventing a new tolerance regime.
_HOLD_S = 0.4
_POLL_MARGIN_S = 0.2


# ---------------------------------------------------------------------------
# Axis 1 -- acquire_driver() / enter_auto_loop() atomic mode+slot claim
# ---------------------------------------------------------------------------


class _StretchedAcquireLock(ControlLock):
    """Test-only subclass: acquire_driver()'s REAL check-then-claim body,
    copied verbatim, with one addition -- an artificial sleep INSIDE the
    same `with self._lock:` block, so a concurrent racer gets a real,
    generous wall-clock window to try to slip in. `_entered_hold` fires
    the instant the checks pass and the lock is genuinely held, so the
    test can synchronize on "the hold has started" instead of guessing
    at thread-scheduling timing. Never touches control_lock.py itself."""

    def __init__(self, hold_s):
        super().__init__()
        self.hold_s = hold_s
        self.entered_hold = threading.Event()

    def acquire_driver(self):
        with self._lock:
            if self._mode != MODE_AI_PILOT:
                if self._mode == MODE_HUMAN:
                    raise ControlModeConflict("controller_locked_by_human")
                if self._mode == MODE_AUTO_LOOP:
                    raise ControlModeConflict("controller_locked_by_auto_loop")
                raise ControlModeConflict(f"controller_locked:{self._mode}")
            if self._driving:
                raise ControlModeConflict("controller_busy")
            self.entered_hold.set()
            time.sleep(self.hold_s)  # the stretch -- still INSIDE the one lock hold
            self._driving = True


class _StretchedEnterAutoLoopLock(ControlLock):
    """Mirrors _StretchedAcquireLock in the REVERSE direction --
    enter_auto_loop()'s real body, stretched the same way, to prove a
    concurrent acquire_driver() racer can't slip through while an
    AUTO-LOOP start is mid-check either."""

    def __init__(self, hold_s):
        super().__init__()
        self.hold_s = hold_s
        self.entered_hold = threading.Event()

    def enter_auto_loop(self):
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("locked_by_human_attach")
            if self._mode == MODE_AUTO_LOOP:
                raise ControlModeConflict("already_running")
            if self._driving:
                raise ControlModeConflict("locked_by_active_driver")
            self.entered_hold.set()
            time.sleep(self.hold_s)  # the stretch -- still INSIDE the one lock hold
            self._mode = MODE_AUTO_LOOP


class _NaiveTwoStepAcquireLock(ControlLock):
    """The deliberately BROKEN variant -- reproduces the exact pre-P0-fix
    shape acquire_driver()'s own docstring describes as the historical
    bug: the mode check and the driver-slot claim are two SEPARATE lock
    acquisitions, with the artificial stretch landing in the GAP between
    them (lock released) instead of inside one continuous hold. Proves
    the green tests above are sensitive to a real violation, not just
    "green because nothing was tried" -- against THIS variant, the same
    racer technique DOES interleave."""

    def __init__(self, hold_s):
        super().__init__()
        self.hold_s = hold_s
        self.entered_gap = threading.Event()

    def acquire_driver(self):
        with self._lock:
            mode = self._mode
        if mode != MODE_AI_PILOT:
            if mode == MODE_HUMAN:
                raise ControlModeConflict("controller_locked_by_human")
            if mode == MODE_AUTO_LOOP:
                raise ControlModeConflict("controller_locked_by_auto_loop")
            raise ControlModeConflict(f"controller_locked:{mode}")
        self.entered_gap.set()
        time.sleep(self.hold_s)  # the GAP -- lock is NOT held here, unlike the real fix
        with self._lock:
            # Only re-checks `_driving`, never mode -- the exact
            # pre-P0-fix omission acquire_driver()'s docstring names.
            if self._driving:
                raise ControlModeConflict("controller_busy")
            self._driving = True


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

    # Poll EARLY, well before the hold finishes: take_human() must still
    # be blocked on self._lock.acquire() -- if it already resolved here,
    # it interleaved mid-window, exactly the TOCTOU this claims not to have.
    time.sleep(_POLL_MARGIN_S)
    assert "outcome" not in result, "take_human() returned WHILE acquire_driver() still held the lock -- TOCTOU"

    driver_thread.join(timeout=2.0)
    racer_thread.join(timeout=2.0)
    assert result["outcome"] == "took_human"
    # The driver slot the racer could have stolen is intact -- nothing
    # about the eventual take_human() unwound the AI's own claim.
    assert lock.is_driving() is True


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
    assert "outcome" not in result, "acquire_driver() returned WHILE enter_auto_loop() still held the lock -- TOCTOU"

    driver_thread.join(timeout=2.0)
    racer_thread.join(timeout=2.0)
    # Once enter_auto_loop() actually commits MODE_AUTO_LOOP, the racing
    # acquire_driver() correctly sees the NEW mode -- not a stale
    # ai_pilot read cached from before the hold.
    assert result["outcome"] == "controller_locked_by_auto_loop"
    assert lock.mode == MODE_AUTO_LOOP
    assert lock.is_driving() is False


def test_naive_two_step_acquire_driver_lets_take_human_interleave_mid_gap():
    """Sensitivity check -- same racer technique as the two tests above,
    run against the deliberately broken two-step variant. If this test
    did NOT catch the interleave, the green tests above would be
    meaningless (they'd pass against a broken acquire_driver() too, for
    lack of trying). It does catch it: take_human() slips through
    DURING the unprotected gap, and the naive acquire_driver -- having
    never re-checked mode after the gap -- claims the driver slot anyway.
    Result: MODE_HUMAN and is_driving()==True simultaneously, the exact
    two-writer state TW-04 exists to prevent."""
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

    # take_human() ran to completion INSIDE the gap -- driver_thread is
    # still asleep in its (unprotected) hold at this point.
    assert result["outcome"] == "took_human"
    assert lock.mode == MODE_HUMAN

    driver_thread.join(timeout=2.0)
    # The naive acquire_driver claims the slot anyway, oblivious that
    # mode flipped to HUMAN in the gap it left open.
    assert lock.is_driving() is True


# ---------------------------------------------------------------------------
# Axis 2 -- take_human()'s no-_driving-check asymmetry, end-to-end
# ---------------------------------------------------------------------------


def _block_wait_settle(release_event, timeout=2.0):
    """Same fixture-shape as test_active_driver.py's own helper of the
    same name -- a `wait_settle` stand-in that blocks until released,
    keeping a `do` dispatch's driver slot held open on demand."""

    def _wait_settle(wait_prompt=None, timeout=8.0, debounce_ms=350):
        release_event.wait(timeout=timeout)
        return "idle", 0.0

    return _wait_settle


def test_take_human_succeeds_instantly_but_the_keystroke_waits_for_the_fenced_dispatch_to_release(fake_daemon):
    """WO-CLEANPREEMPT fix -- the SAME scenario the module's original
    Axis-2 finding documented (a `tw attach` connecting while a `do`
    dispatch is deliberately held mid-`wait_settle()`), assertions
    FLIPPED to match the fix, proven live against the real daemon
    (ThreadingUnixServer/CommandHandler/_driving_dispatch, unmodified).

    take_human() still succeeds INSTANTLY -- never refuses, never blocks
    just because an ai_pilot dispatch is mid-flight (the human always
    wins immediately; enter_auto_loop()'s symmetric
    `locked_by_active_driver` refusal is deliberately NOT mirrored here).
    But the dispatch caught mid-flight is now FENCED
    (control_lock.is_driver_fenced()), and the human's own keystroke
    -- session.send_raw()'s bounded fence-wait -- is held off the wire
    until that fenced dispatch's send-then-settle window actually
    closes. Zero interleave, a clean cutover, and take_human() itself
    never waited on any of it."""
    release = threading.Event()
    fake_daemon.session.wait_settle = _block_wait_settle(release)

    do_result = {}

    def do_call():
        do_result["resp"] = send_request(fake_daemon.sock_path, "do", {"input": "ai-action"})

    do_thread = threading.Thread(target=do_call)
    do_thread.start()
    # Generous margin (matches test_active_driver.py's own convention) --
    # not a race against acquire_driver() itself, which happens
    # synchronously before send()/wait_settle() even start.
    time.sleep(0.2)

    assert fake_daemon.control_lock.is_driving() is True
    assert fake_daemon.control_lock.mode == MODE_AI_PILOT

    conn = AttachInputConn(fake_daemon.sock_path)
    try:
        # take_human() succeeds instantly -- no locked_by_active_driver-
        # style refusal exists on this path, unchanged by the fix.
        assert conn.connect() is True
        assert fake_daemon.control_lock.mode == MODE_HUMAN
        # Both true AT ONCE: the ai_pilot dispatch is still mid-flight
        # (never aborted), AND a human now holds MODE_HUMAN -- but it is
        # now FENCED, unlike before the fix.
        assert fake_daemon.control_lock.is_driving() is True
        assert fake_daemon.control_lock.is_driver_fenced() is True

        # The keystroke send is now BLOCKED inside send_raw()'s bounded
        # fence-wait -- issue it on its own thread so this test can
        # observe it NOT landing while the fenced dispatch is still
        # mid-flight.
        key_result = {}

        def send_key_call():
            key_result["ok"] = conn.send_key(b"H")

        key_thread = threading.Thread(target=send_key_call)
        key_thread.start()
        time.sleep(0.2)

        # Neither side has resolved: the human keystroke is waiting on
        # the fence, and the ai_pilot dispatch is still waiting on
        # wait_settle() -- the clean cutover this fix enforces, in
        # contrast to the pre-fix interleave this test used to prove.
        assert fake_daemon.session.raw_sent == []
        assert "resp" not in do_result
        assert "ok" not in key_result

        release.set()
        do_thread.join(timeout=2.0)
        key_thread.join(timeout=2.0)

        # NOW the keystroke lands -- strictly AFTER the fenced dispatch
        # released, never interleaved with it.
        assert do_result["resp"]["ok"] is True
        assert key_result["ok"] is True
        assert fake_daemon.session.raw_sent == [b"H"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Verdict (Mack, 2026-07-20; fix landed WO-CLEANPREEMPT, 2026-07-20)
# ---------------------------------------------------------------------------
# Axis 1: RACE-FREE. acquire_driver()/enter_auto_loop() share ONE lock,
# check-then-claim under the same hold, in both directions -- proven by
# forcing a real racer thread to sit blocked for the full artificial
# hold, and by showing the SAME racer technique interleaves the instant
# the hold is split into two acquisitions (the naive variant). Untouched
# by WO-CLEANPREEMPT -- still green, unmodified.
#
# Axis 2 (ORIGINAL FINDING, pre-fix): REAL, REACHABLE GAP -- not a
# documented "human always preempts" design. take_human()'s docstring
# only discussed stealing the keyboard from another attach or a running
# LoopPlayer; nothing documented (or defended) ignoring an in-flight
# ai_pilot driver, and nothing analogous to enter_auto_loop()'s
# `locked_by_active_driver` check existed for it. Concrete scenario: an
# operator runs `tw do "<slow-settling command>"` (e.g. a real
# multi-second server-side transition), then attaches mid-flight via
# `tw attach` -- ordinary, documented normal use, no attacker involved.
# take_human() succeeded immediately; the human's very first keystroke
# reached session.send_raw() -- gated on nothing but send_lock's
# byte-level mutex, never on control_lock at all -- while the ai_pilot
# dispatch's own session.send()+wait_settle() window was still open on
# the SAME telnet connection. wait_settle() (settle.py) has zero
# awareness of who caused an rx byte to arrive; it only watches
# rx_count/last_rx. So the ai_pilot dispatch's eventual
# build_response()/ledger entry attributed whatever the server sent
# back -- shaped by BOTH the AI's own action AND the human's injected
# keystroke -- entirely to the AI's single logged input, corrupting
# `_record_ledger`'s pre/post-text diff (and therefore the skills/miner
# pattern-learning substrate) with a false action->outcome mapping.
# This was exactly the two-writer class TW-04 exists to prevent, reached
# through take_human()'s unchecked path rather than a second concurrent
# `do`.
#
# FIX (WO-CLEANPREEMPT): take_human() still never refuses/blocks on
# `_driving` (the human always wins immediately -- that invariant is
# preserved, not weakened), but now FENCES the caught-mid-flight
# dispatch (`ControlLock.is_driver_fenced()`). Two consumers of the
# fence close the gap from both ends: `Session.send_raw()` holds the
# human's own keystroke off the wire until the fenced dispatch's
# `release_driver()` actually runs (a bounded wait, proven above --
# zero interleave, a clean cutover), and protocol.py's do/send/haggle
# call sites flag their own eventual ledger entry
# `interrupted_by_human=True` when they were the ones fenced, so a
# pattern-learning consumer can exclude a corrupted mapping instead of
# silently trusting it. See tests/test_clean_preempt.py for the
# ledger-flagging + attach-ledger-routing proofs.
