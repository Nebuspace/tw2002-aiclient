"""LoopPlayer (twclient/loop_player.py) -- the AUTO-LOOP background
driver. No sockets, no curses, no real network -- a FakeLoopSession
mirrors replay_skill()'s actual usage (send/wait_settle/render/
render_text), and a FakeWatchHub just captures broadcast_extra() calls
into a list so progress-event shape/ordering is directly assertable.
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
    again."""

    def __init__(self, screen=_MAIN_COMMAND_SCREEN, cycle_delay_s=0.05):
        self._screen = screen
        self.cycle_delay_s = cycle_delay_s
        self.sent = []

    def send(self, text, enter=True, secret=False):
        self.sent.append(text)

    def wait_settle(self, wait_prompt=None, timeout=8.0):
        time.sleep(self.cycle_delay_s)
        return "idle", self.cycle_delay_s

    def render(self):
        return self._screen.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())


class FakeWatchHub:
    def __init__(self):
        self.events = []

    def broadcast_extra(self, event):
        self.events.append(event)


def _skill(n_steps=1):
    return {
        "name": "test-loop",
        "steps": [
            {"input": "d", "wait_prompt": None, "expected_post_class": "main_command"} for _ in range(n_steps)
        ],
    }


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

    player.start(_skill(), "test-loop", cycles=3)
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

    player.start(_skill(), "test-loop", cycles=1)
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

    player.start(_skill(n_steps=1), "slow-loop", cycles=50)  # plenty of time to still be running
    with pytest.raises(LoopPlayerError):
        player.start(_skill(), "test-loop", cycles=1)
    player.stop()
    _wait_until(lambda: not player.running)


def test_stop_halts_before_all_cycles_complete():
    session = FakeLoopSession()
    lock = ControlLock()
    hub = FakeWatchHub()
    player = LoopPlayer(session, lock, hub)

    player.start(_skill(), "test-loop", cycles=50)
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

    player.start(_skill(), "test-loop", cycles=50)
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
        "running": False, "paused": False, "name": None, "cycle": 0, "cycles_total": 0, "last_result": None,
    }

    player.start(_skill(), "test-loop", cycles=2)
    assert _wait_until(lambda: not player.running)
    snap = player.snapshot()
    assert snap["running"] is False
    assert snap["name"] == "test-loop"
    assert snap["cycle"] == 2
    assert snap["cycles_total"] == 2
    assert snap["last_result"] == "cycles_complete"


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
