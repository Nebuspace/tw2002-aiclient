"""LoopPlayer (twclient/loop_player.py) -- the AUTO-LOOP background
driver. No sockets, no curses, no real network -- a FakeLoopSession
mirrors replay_skill()'s actual usage (the full settle-detection
protocol surface send_and_confirm needs, plus render/render_text), and a
FakeWatchHub just captures broadcast_extra() calls into a list so
progress-event shape/ordering is directly assertable.
"""

import time

import pytest

from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, ControlLock
from twclient.loop_player import LoopPlayer, LoopPlayerError

# A real classify.py anchor (same literal prompt test_spectate_app.py's
# _SAMPLE_EVENT uses) -- classifies as "main_command", so replay_skill()
# never sees a surprise unless a test deliberately wants one.
_MAIN_COMMAND_SCREEN = "Command [TL=00:00:08]:[1234] (?=Help)? :"


class FakeLoopSession:
    """`cycle_delay_s` paces each simulated settle -- without it, a
    50-cycle "slow loop" (used to give a test room to call stop()/
    pause() mid-run) would blast through every cycle in well under a
    millisecond and finish before the test thread ever gets scheduled
    again.

    TW-02: `replay_skill()` now drives its send through
    `settle.send_and_confirm`, which needs the full settle-detection
    protocol surface (`clock()`/`rx_count`/`last_rx`/`sleep()`), not just
    `send()`/`wait_settle()`/`render()`. LoopPlayer runs `replay_skill()`
    inside a REAL background thread, so `sleep()` still needs to cost a
    little REAL wall-clock time (so the test driver's own real-time
    polling can interleave and observe/interrupt mid-run state) -- but
    only ONCE per send, not on every debounce poll iteration
    `send_and_confirm`'s idle-fallback makes internally: `send()` marks
    an advance pending; the FIRST subsequent `sleep()` call pays the
    real `cycle_delay_s` delay and resolves it (rx_count bumps, `last_rx`
    lands on the FAKE clock `self.t`, mirroring `test_skills.py`'s
    `FakeReplaySession`); every later `sleep()` call in that same settle
    wait (debounce accumulation, the stability re-check) costs no
    further real time, so one whole confirm still costs ~cycle_delay_s
    of real time end to end, matching the original pacing."""

    def __init__(self, screen=_MAIN_COMMAND_SCREEN, cycle_delay_s=0.05):
        self._screen = screen
        self.cycle_delay_s = cycle_delay_s
        self.sent = []
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._pending_advance = False

    def clock(self):
        return self.t

    def sleep(self, seconds):
        if self._pending_advance:
            time.sleep(self.cycle_delay_s)
            self._pending_advance = False
            self.t += seconds
            self.rx_count += 1
            self.last_rx = self.t
        else:
            self.t += seconds

    def send(self, text, enter=True, secret=False):
        self.sent.append(text)
        self._pending_advance = True

    def render(self):
        return self._screen.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())


class FakeWatchHub:
    def __init__(self):
        self.events = []

    def broadcast_extra(self, event):
        self.events.append(event)


def _skill(n_steps=1, start_anchor=None):
    return {
        "name": "test-loop",
        "start_anchor": start_anchor,
        "steps": [
            {"input": "d", "wait_prompt": None, "expected_post_class": "main_command"} for _ in range(n_steps)
        ],
    }


class _RecordingLedger:
    """Same fake as tests/test_skills.py's -- pins down the TW-04
    interface contract skills.replay_skill()/LoopPlayer code against
    (actor="trainer", session_id=...), since this worktree's ledger.py
    doesn't have the real signature yet (a sibling lane's in-flight
    change, proven at integration)."""

    def __init__(self):
        self.calls = []

    def record_do(self, pre_text, input_text, secret, post_text, settled_class, capture=None, actor=None, session_id=None):
        self.calls.append(
            dict(
                pre_text=pre_text,
                input_text=input_text,
                secret=secret,
                post_text=post_text,
                settled_class=settled_class,
                capture=capture,
                actor=actor,
                session_id=session_id,
            )
        )


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_start_runs_all_cycles_and_broadcasts_progress_per_cycle():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(), "test-loop", cycles=3, force=True)  # _skill() has no start_anchor (TW-03)
    assert _wait_until(lambda: not player.running)

    assert player.cycles_done == 3
    assert player.last_result == "cycles_complete"
    assert session.sent == ["d", "d", "d"]
    # 3 per-cycle progress events + 1 final "done" event
    assert len(hub.events) == 4
    assert [e["cycle"] for e in hub.events] == [1, 2, 3, 3]
    assert hub.events[-1]["done"] is True
    assert hub.events[-1]["result"] == "cycles_complete"
    assert all(e["kind"] == "play_progress" for e in hub.events)


def test_start_enters_auto_loop_mode_and_leaves_it_on_completion():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(), "test-loop", cycles=1, force=True)  # _skill() has no start_anchor (TW-03)
    assert lock.mode == MODE_AUTO_LOOP  # observable mid-run
    assert _wait_until(lambda: not player.running)
    assert lock.mode == MODE_AI_PILOT  # released on completion


def test_start_refuses_when_control_lock_is_human_attached():
    session = FakeLoopSession()
    lock = ControlLock()
    lock.take_human()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    with pytest.raises(Exception):  # ControlModeConflict -- propagated straight through
        player.start(_skill(), "test-loop", cycles=1)
    assert player.running is False
    assert lock.mode == "human"  # untouched by the refused start


def test_start_refuses_cycles_beyond_the_hard_cap():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    with pytest.raises(LoopPlayerError):
        player.start(_skill(), "test-loop", cycles=51)
    assert player.running is False
    assert lock.mode == MODE_AI_PILOT  # never entered auto_loop for a rejected request


def test_start_refuses_when_already_running():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(n_steps=1), "slow-loop", cycles=50, force=True)  # plenty of time to still be running
    with pytest.raises(LoopPlayerError):
        player.start(_skill(), "test-loop", cycles=1, force=True)
    player.stop()
    _wait_until(lambda: not player.running)


def test_stop_halts_before_all_cycles_complete():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(), "test-loop", cycles=50, force=True)  # _skill() has no start_anchor (TW-03)
    assert _wait_until(lambda: player.cycles_done >= 1)
    player.stop()
    assert _wait_until(lambda: not player.running)

    assert player.last_result == "stopped"
    assert player.cycles_done < 50
    assert lock.mode == MODE_AI_PILOT


def test_pause_blocks_progress_until_resumed():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(), "test-loop", cycles=50, force=True)  # _skill() has no start_anchor (TW-03)
    assert _wait_until(lambda: player.cycles_done >= 1)
    player.pause()
    assert player.paused is True
    # pause() only takes effect at the NEXT cycle boundary (an in-flight
    # cycle is never aborted mid-way) -- let that one settle before
    # capturing the baseline, or the assertion below races it.
    time.sleep(0.15)
    stalled_at = player.cycles_done
    time.sleep(0.3)  # long enough that more cycles WOULD have run if not paused
    assert player.cycles_done == stalled_at
    assert player.running is True  # still alive, just parked

    player.resume()
    assert _wait_until(lambda: player.cycles_done > stalled_at)
    player.stop()
    _wait_until(lambda: not player.running)


def test_pause_and_resume_raise_when_not_running():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    with pytest.raises(LoopPlayerError):
        player.pause()
    with pytest.raises(LoopPlayerError):
        player.resume()


def test_floor_halts_before_a_cycle_that_would_start_at_or_below_it():
    session = FakeLoopSession(screen="You have 100 credits.\nCommand [TL=00:00:08]:[1234] (?=Help)? :")
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(), "test-loop", cycles=5, floor=200)
    assert _wait_until(lambda: not player.running)

    assert player.last_result == "floor_reached"
    assert player.cycles_done == 0
    assert session.sent == []  # never even attempted a cycle


def test_snapshot_reflects_live_progress():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    assert player.snapshot() == {
        "running": False, "paused": False, "name": None, "cycle": 0, "cycles_total": 0,
        "last_result": None, "last_error": None,
    }

    player.start(_skill(), "test-loop", cycles=2, force=True)  # _skill() has no start_anchor (TW-03)
    assert _wait_until(lambda: not player.running)
    snap = player.snapshot()
    assert snap["running"] is False
    assert snap["name"] == "test-loop"
    assert snap["cycle"] == 2
    assert snap["cycles_total"] == 2
    assert snap["last_result"] == "cycles_complete"


# -- TW-03/TW-04: start_anchor guard + ledgering, threaded through LoopPlayer ------


def test_start_refuses_unanchored_skill_without_force():
    """A skill with no start_anchor (TW-03) must not silently replay --
    the guard's SkillError is caught inside _run() (not left to escape
    uncaught out of the background thread) and reported as a clean
    last_result="refused"/last_error, with cycles_done staying 0 and
    zero keystrokes sent; cleanup (leave_auto_loop) still runs."""
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(), "test-loop", cycles=3)  # force defaults to False
    assert _wait_until(lambda: not player.running)
    assert player.last_result == "refused"
    assert "missing_start_anchor" in player.last_error
    assert player.cycles_done == 0
    assert session.sent == []
    assert lock.mode == MODE_AI_PILOT  # cleanup still released the lock


def test_start_halts_on_start_anchor_mismatch():
    """FakeLoopSession's screen is static (send() doesn't change it), so
    this fires at cycle 0 -- the genuinely mid-run "loop wandered off its
    anchor sector" case is exercised end-to-end via the exact same
    replay_skill() call in tests/test_skills.py's
    test_play_skill_halts_on_start_anchor_mismatch_mid_run; LoopPlayer
    just needs to funnel that ReplayDivergence into last_result the same
    way it already does for a post-class surprise."""
    session = FakeLoopSession(screen="Sector : 100\n" + _MAIN_COMMAND_SCREEN)
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(start_anchor=999), "test-loop", cycles=5)
    assert _wait_until(lambda: not player.running)

    assert player.last_result == "surprise"
    assert player.cycles_done == 0
    assert session.sent == []


def test_start_forwards_ledger_and_session_id_to_every_send():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    ledger = _RecordingLedger()
    player = LoopPlayer(session, lock, hub, ledger=ledger, session_id="s-loop-9")

    player.start(_skill(n_steps=2), "test-loop", cycles=2, force=True)  # unanchored -- see force
    assert _wait_until(lambda: not player.running)

    assert len(ledger.calls) == 4  # 2 cycles * 2 steps
    assert all(c["actor"] == "trainer" for c in ledger.calls)
    assert all(c["session_id"] == "s-loop-9" for c in ledger.calls)


def test_leave_auto_loop_from_a_finishing_thread_never_clobbers_a_later_mode():
    """If a human attaches the instant a run finishes, the finishing
    thread's own leave_auto_loop() call must not stomp it back to
    ai_pilot -- leave_auto_loop() only acts while mode is STILL
    auto_loop (see control_lock.py). Simulated directly since racing a
    real thread against a real attach deterministically is impractical."""
    lock = ControlLock()
    lock.enter_auto_loop()
    lock.leave_auto_loop()
    lock.take_human()
    lock.leave_auto_loop()  # a stale call, as if a slow finishing thread's cleanup ran late
    assert lock.mode == "human"
