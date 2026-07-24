"""tw2002_aiclient.session.control_lock — who may drive the ONE game connection.

Canon modes are exactly ``{app, human, spectate}`` — the AI never live-drives
(see architecture/control-and-escalation.md). A background LoopPlayer still
has an exclusive hold, but that hold **collapses to mode ``app``** (not a
third drive mode name on the wire).

  MODE_APP (default)  -- App may drive (taught-screen autopilot / do-family
                         dispatch). EXCLUSIVE-per-dispatch: acquire_driver() /
                         release_driver() reserve a single active-driver slot
                         so two concurrent one-shot CLI drives never interleave
                         on the wire. A second concurrent claim is refused
                         outright (``controller_busy``), never queued.
  MODE_HUMAN          -- interactive ``tw attach`` holds the keyboard. Every
                         other driver is refused (``controller_locked_by_human``).
                         take_human() always wins immediately over App (and over
                         an in-flight App dispatch — that dispatch is FENCED,
                         not refused). A second take_human() while already
                         attached raises ``already_attached``.
  MODE_SPECTATE       -- paused / read-only standing state. Nobody may acquire
                         the driver slot (typed ``spectate_read_only``).

auto_loop is not a mode string: enter_auto_loop() / leave_auto_loop() mark an
exclusive App hold while ``mode`` stays ``app``. set_mode() cannot enter or
clobber that hold, and cannot enter MODE_HUMAN (attach-scoped only).
"""

from __future__ import annotations

import threading

MODE_APP = "app"
MODE_HUMAN = "human"
MODE_SPECTATE = "spectate"

# Legacy alias accepted only as a *collapse target* documentation token —
# never returned by ``mode`` and never a set_mode() destination.
_AUTO_LOOP_ALIAS = "auto_loop"

_SETTABLE_MODES = frozenset({MODE_APP, MODE_SPECTATE})
_ALL_MODES = frozenset({MODE_APP, MODE_HUMAN, MODE_SPECTATE})


class ControlModeConflict(Exception):
    """Raised when a mode transition or driver reservation is rejected.

    Typical messages (refuse-not-queue — never blocked waiting):
      ``already_attached`` / ``locked_by_human_attach`` /
      ``already_running`` / ``locked_by_active_driver`` /
      ``controller_locked_by_human`` / ``controller_locked_by_auto_loop`` /
      ``controller_busy`` / ``spectate_read_only`` /
      ``locked_by_auto_loop``.
    """


class ControlLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._mode = MODE_APP
        # Exclusive LoopPlayer hold — mode stays MODE_APP while this is True.
        self._auto_loop_held = False
        # Active do/send-family dispatch slot (orthogonal to mode; only
        # claimable while mode == MODE_APP and not auto_loop-held).
        self._driving = False
        # WO-CLEANPREEMPT: take_human() found an in-flight App dispatch and
        # granted anyway — fence it so Session.send_raw can hold the human's
        # first keystroke off the wire until release_driver().
        self._driver_fenced = False

    @property
    def mode(self):
        with self._lock:
            return self._mode

    def app_may_send(self):
        """True when standing mode is App (including an auto_loop App hold).

        Spectate and Human never grant App send. Callers that need the
        exclusive active-driver slot still go through acquire_driver().
        """
        with self._lock:
            return self._mode == MODE_APP

    def is_auto_loop_held(self):
        """True while LoopPlayer's exclusive App hold is active."""
        with self._lock:
            return self._auto_loop_held

    # -- exclusive, connection-scoped (tw attach) ------------------------

    def take_human(self):
        """Claim the keyboard for an interactive attach.

        Always succeeds over App (including an auto_loop App hold and an
        in-flight App dispatch). Refuses only a second attach
        (``already_attached``). When an App dispatch is mid-flight,
        fences it (``is_driver_fenced``) instead of blocking or refusing.
        """
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("already_attached")
            if self._driving:
                self._driver_fenced = True
            self._auto_loop_held = False
            self._mode = MODE_HUMAN

    def release_human(self):
        """Idempotent — always returns to MODE_APP (defensive cleanup)."""
        with self._lock:
            self._mode = MODE_APP
            # Attach release never invents an auto_loop hold.
            self._auto_loop_held = False

    def is_driver_fenced(self):
        """Duck-typed by Session.send_raw — True while a fenced App dispatch
        still holds the driver slot after take_human() preempted it."""
        with self._lock:
            return self._driver_fenced

    # -- exclusive, dispatch-scoped (TW-04: one in-flight App driver) ----

    def acquire_driver(self):
        """Atomically claim the single active-driver slot for one App dispatch.

        Mode and slot are checked under one lock hold. Refused outright
        (never queued) with a typed reason:
          - human attach → ``controller_locked_by_human``
          - spectate → ``spectate_read_only``
          - auto_loop exclusive hold → ``controller_locked_by_auto_loop``
          - slot already held → ``controller_busy``
        """
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("controller_locked_by_human")
            if self._mode == MODE_SPECTATE:
                raise ControlModeConflict("spectate_read_only")
            if self._mode != MODE_APP:
                raise ControlModeConflict(f"controller_locked:{self._mode}")
            if self._auto_loop_held:
                raise ControlModeConflict("controller_locked_by_auto_loop")
            if self._driving:
                raise ControlModeConflict("controller_busy")
            self._driving = True
            self._driver_fenced = False

    def release_driver(self):
        """Idempotent — clears the driver slot and any fence on it."""
        with self._lock:
            self._driving = False
            self._driver_fenced = False

    def is_driving(self):
        with self._lock:
            return self._driving

    # -- exclusive App hold (LoopPlayer) — collapses to mode app ---------

    def enter_auto_loop(self):
        """Mark exclusive App hold for a background LoopPlayer.

        Mode becomes/stays MODE_APP (auto_loop is not a third mode string).
        Refuses human attach, a second enter, or an in-flight App driver.
        """
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("locked_by_human_attach")
            if self._auto_loop_held:
                raise ControlModeConflict("already_running")
            if self._driving:
                raise ControlModeConflict("locked_by_active_driver")
            self._mode = MODE_APP
            self._auto_loop_held = True

    def leave_auto_loop(self):
        """Idempotent — clears the exclusive App hold only if held.

        Never clobbers a DIFFERENT mode (e.g. human attach that landed
        while the loop was finishing).
        """
        with self._lock:
            if not self._auto_loop_held:
                return
            # Clear the exclusive hold only. Mode stays whatever it is —
            # take_human() may already have flipped to MODE_HUMAN.
            self._auto_loop_held = False

    # -- plain standing-state toggle (control panel / panic) -------------

    def set_mode(self, new_mode):
        """Non-exclusive standing toggle between app and spectate.

        Raises ValueError for unknown / non-settable names (including
        ``human`` and the collapsed ``auto_loop`` alias). Raises
        ControlModeConflict if a human attach or auto_loop hold is active.
        """
        if new_mode == _AUTO_LOOP_ALIAS:
            raise ValueError(f"not a settable mode: {new_mode!r} (collapses to {MODE_APP!r})")
        if new_mode not in _SETTABLE_MODES:
            raise ValueError(f"not a settable mode: {new_mode!r}")
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("locked_by_human_attach")
            if self._auto_loop_held:
                raise ControlModeConflict("locked_by_auto_loop")
            self._mode = new_mode
