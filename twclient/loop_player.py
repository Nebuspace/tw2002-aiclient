"""twclient/loop_player.py — the AUTO-LOOP background driver (Trainer
Control Panel, TUI-POLISH-PLAN.md).

Runs a saved skill (twclient.skills.replay_skill -- READ-ONLY use, this
module never edits skills.py's replay internals; Wave 3b later makes
replay_skill haggle-robust, this loop just uses whatever replay_skill
currently does) as a background thread, so the spectator TUI can watch
it live and start/pause/stop it -- unlike `tw play`'s existing verb
(protocol.py's `_dispatch_play`), which blocks the calling socket
connection until the WHOLE run completes and has no pause/stop hooks at
all.

Broadcasts one "play_progress" event per cycle boundary via
WatchHub.broadcast_extra() -- a plain event pushed into the SAME
subscriber queues `tw watch`/`tw spectate` already read from, no second
stream -- so the spectator's control strip can render a live
cycle-progress bar with zero polling.

Owns the control-lock's MODE_AUTO_LOOP transition (control_lock.py's
enter_auto_loop()/leave_auto_loop()) -- entering/leaving is THIS
module's job alone, never the generic `set_mode` verb (see
control_lock.py's module docstring for why: auto_loop must never read
as "on" without an actually-running thread behind it).
"""

import threading
import time

from .control_lock import ControlModeConflict
from .ledger import snapshot_state
from .skills import ReplayDivergence, replay_skill

_PAUSE_POLL_S = 0.1

# This repo's hard-cap ethos (see skills.py's own _MAX_PLAY_CYCLES)
# applied independently here -- an unattended AUTO-LOOP background
# thread cannot be armed for more than this regardless of caller intent.
_MAX_CYCLES = 50


class LoopPlayerError(Exception):
    """A start/pause/resume/stop request that doesn't apply to the
    player's current state (e.g. starting while already running)."""


class LoopPlayer:
    def __init__(self, session, control_lock, watch_hub):
        self.session = session
        self.control_lock = control_lock
        self.watch_hub = watch_hub
        self._state_lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self.skill_name = None
        self.cycles_total = 0
        self.cycles_done = 0
        self.floor = None
        self.last_result = None  # None while running; else "cycles_complete" | "surprise" | "floor_reached" | "stopped"

    @property
    def running(self):
        with self._state_lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):
        return self._pause.is_set()

    def start(self, skill, name, cycles, floor=None, params=None, step_timeout=8.0):
        """Raises LoopPlayerError if a run is already active or `cycles`
        exceeds the hard cap, ControlModeConflict if the control-lock
        refuses (human attached, or -- belt and suspenders -- somehow
        already in auto_loop)."""
        if cycles > _MAX_CYCLES:
            raise LoopPlayerError(f"cycles_exceeds_cap:{cycles}>{_MAX_CYCLES}")
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                raise LoopPlayerError("already_running")
            self.control_lock.enter_auto_loop()  # raises ControlModeConflict on refusal
            self.skill_name = name
            self.cycles_total = cycles
            self.cycles_done = 0
            self.floor = floor
            self.last_result = None
            self._stop.clear()
            self._pause.clear()
            self._thread = threading.Thread(
                target=self._run, args=(skill, params or {}, step_timeout), daemon=True
            )
            self._thread.start()

    def pause(self):
        if not self.running:
            raise LoopPlayerError("not_running")
        self._pause.set()

    def resume(self):
        if not self.running:
            raise LoopPlayerError("not_running")
        self._pause.clear()

    def stop(self, join_timeout=2.0):
        """Signals the loop to exit at its next cycle boundary -- never
        aborts a cycle mid-flight (same "don't press on past a surprise"
        discipline replay_skill() already has for a single cycle).
        Idempotent/safe to call when nothing is running.

        Joins the thread for up to `join_timeout` seconds -- bounded,
        not unbounded (a caller like play_stop's protocol dispatch has
        its own socket-level timeout to respect), but long enough that
        in the common case (a cycle boundary check every replay_skill()
        call, which settles in well under a second for ordinary game
        actions) a caller can rely on "stop() returned => the loop has
        actually stopped and control_lock is back to ai_pilot". This is
        load-bearing for the Trainer Control Panel's Panic key, which
        immediately follows stop() with set_mode(spectate) -- caught
        live via the control-panel pty test: without the join, panic's
        second call could race the still-finishing thread's own
        leave_auto_loop() and get rejected with locked_by_auto_loop. If
        a single in-flight cycle is genuinely slow, the join times out
        but the loop still stops eventually regardless."""
        self._stop.set()
        self._pause.clear()  # a paused loop must wake up to see the stop
        thread = self._thread
        if thread is not None:
            thread.join(timeout=join_timeout)

    def snapshot(self):
        """A plain dict of the player's current state -- used by
        protocol.py's `status` verb and play_start/stop/pause responses,
        so a caller never has to poll cycle counts through a second
        channel."""
        return {
            "running": self.running,
            "paused": self.paused,
            "name": self.skill_name,
            "cycle": self.cycles_done,
            "cycles_total": self.cycles_total,
            "last_result": self.last_result,
        }

    def _run(self, skill, params, step_timeout):
        result = "cycles_complete"
        try:
            for cycle in range(self.cycles_total):
                while self._pause.is_set() and not self._stop.is_set():
                    time.sleep(_PAUSE_POLL_S)
                if self._stop.is_set():
                    result = "stopped"
                    break
                if self.floor is not None:
                    text = self.session.render_text(self.session.render())
                    credits = snapshot_state(text).get("credits")
                    if credits is not None and credits <= self.floor:
                        result = "floor_reached"
                        break
                try:
                    replay_skill(self.session, skill, params=params, step_timeout=step_timeout)
                except ReplayDivergence:
                    result = "surprise"
                    break
                self.cycles_done = cycle + 1
                self._broadcast_progress()
        finally:
            self.last_result = result
            try:
                self.control_lock.leave_auto_loop()
            except ControlModeConflict:
                pass  # defensive -- leave_auto_loop() itself never raises, but never crash cleanup either way
            self._broadcast_progress(done=True)

    def _broadcast_progress(self, done=False):
        hub = self.watch_hub
        if hub is None:
            return
        hub.broadcast_extra(
            {
                "kind": "play_progress",
                "name": self.skill_name,
                "cycle": self.cycles_done,
                "cycles_total": self.cycles_total,
                "done": done,
                "result": self.last_result if done else None,
            }
        )
