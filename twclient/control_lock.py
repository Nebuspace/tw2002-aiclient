"""twclient/control_lock.py — the daemon's control-MODE state machine:
who is currently allowed to drive the ONE game connection.

Extensible mode enum, not a boolean (forward-compat seam for the
Trainer Control Panel, TUI-POLISH-PLAN.md's "Mode selector" --
{ai_pilot, auto_loop, human, spectate}):

  MODE_AI_PILOT (default) -- do/send/play/replay/haggle always succeed;
                   the AI drives.
  MODE_HUMAN    -- an interactive `tw attach` session holds the keyboard;
                   every driving verb from anyone else is REJECTED
                   outright (never queued/interleaved onto the wire).
                   EXCLUSIVE + CONNECTION-SCOPED: only take_human()/
                   release_human() (always paired in one connection's
                   own try/finally -- see daemon.py's
                   CommandHandler._handle_attach) can enter/leave this
                   mode, so a crashed/killed attach session can never
                   wedge the daemon in it. A second take_human() while
                   one is already active is rejected.
  MODE_SPECTATE -- driving paused; nobody's driving (the panel's
                   explicit "pause" state, also `play_stop`'s/panic's
                   landing mode). Not wired to any client's own
                   connection -- `tw spectate` itself stays fully out of
                   this state machine (it never takes control, read-only
                   by construction) -- this mode exists for the panel's
                   `set_mode`/panic calls to land on.
  MODE_AUTO_LOOP -- the daemon's own background LoopPlayer
                   (loop_player.py) is driving a learned skill solo, no
                   external caller involved at all. EXCLUSIVE but NOT
                   connection-scoped (no client connection to tie it to
                   -- the player is a daemon-owned background thread):
                   only enter_auto_loop()/leave_auto_loop() (paired in
                   LoopPlayer's own start/stop, mirroring take_human's
                   discipline) can enter/leave it -- deliberately NOT a
                   set_mode()-settable target, because claiming
                   "auto_loop" without an actually-running player thread
                   behind it would desync the mode from reality.

Two different lifecycles share one `_mode` field:
  - MODE_HUMAN and MODE_AUTO_LOOP are each exclusive, each entered/left
    ONLY via their own dedicated method pair (take_human/release_human,
    enter_auto_loop/leave_auto_loop) -- never via the generic
    set_mode() verb.
  - MODE_AI_PILOT/MODE_SPECTATE are plain standing daemon-state toggles:
    set_mode() is an ordinary call any one-shot protocol verb can make
    (see protocol.py's "set_mode" verb) -- no connection/thread to tie
    it to, nothing to leak if the caller vanishes. set_mode() refuses to
    clobber MODE_HUMAN or MODE_AUTO_LOOP out from under whatever's
    currently holding them.
"""

import threading

MODE_AI_PILOT = "ai_pilot"
MODE_HUMAN = "human"
MODE_SPECTATE = "spectate"
MODE_AUTO_LOOP = "auto_loop"

# Modes set_mode() may switch TO directly. MODE_HUMAN and MODE_AUTO_LOOP
# are deliberately excluded -- each is only enterable via its own
# dedicated, exclusive method pair (see module docstring).
_SETTABLE_MODES = frozenset({MODE_AI_PILOT, MODE_SPECTATE})

# Modes that currently have an active, exclusive holder (a live attach
# connection or a running LoopPlayer thread) -- set_mode() refuses to
# clobber either one out from under its holder.
_EXCLUSIVE_MODES = frozenset({MODE_HUMAN, MODE_AUTO_LOOP})


class ControlModeConflict(Exception):
    """Raised when a mode transition is rejected: take_human() finding
    MODE_HUMAN already held by another attach session, or set_mode()
    finding MODE_HUMAN active (an attach's exclusive hold can't be
    clobbered by a plain mode-set)."""


class ControlLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._mode = MODE_AI_PILOT

    @property
    def mode(self):
        with self._lock:
            return self._mode

    def ai_may_send(self):
        with self._lock:
            return self._mode == MODE_AI_PILOT

    # -- exclusive, connection-scoped (tw attach) ------------------------

    def take_human(self):
        """Refuses to steal the keyboard out from under EITHER another
        attach session (already_attached) OR a running LoopPlayer
        (locked_by_auto_loop) -- the operator stops the loop (panic/play_stop)
        before taking manual control, same as he'd detach before a
        second attach."""
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("already_attached")
            if self._mode == MODE_AUTO_LOOP:
                raise ControlModeConflict("locked_by_auto_loop")
            self._mode = MODE_HUMAN

    def release_human(self):
        """Idempotent -- always leaves MODE_AI_PILOT, even if called
        without a matching take_human() (defensive cleanup path)."""
        with self._lock:
            self._mode = MODE_AI_PILOT

    # -- exclusive, thread-scoped (loop_player.LoopPlayer) ----------------

    def enter_auto_loop(self):
        """Entered only via LoopPlayer.start() (never the generic
        set_mode() verb -- see module docstring). Refuses to preempt an
        active human attach, mirroring take_human()'s own no-stealing
        rule in the other direction."""
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("locked_by_human_attach")
            if self._mode == MODE_AUTO_LOOP:
                raise ControlModeConflict("already_running")
            self._mode = MODE_AUTO_LOOP

    def leave_auto_loop(self):
        """Idempotent -- returns to MODE_AI_PILOT only if auto_loop was
        actually the current mode (a stale/duplicate call from a
        finishing thread must never clobber a DIFFERENT mode that was
        legitimately set in the meantime, e.g. a human attaching the
        instant the loop finished)."""
        with self._lock:
            if self._mode == MODE_AUTO_LOOP:
                self._mode = MODE_AI_PILOT

    # -- plain standing-state toggle (future control panel) --------------

    def set_mode(self, new_mode):
        """A one-shot, non-exclusive mode switch -- no connection/thread
        lifetime involved, so nothing to release if the caller never
        calls back. Raises ValueError for an unknown/not-directly-
        settable mode name, ControlModeConflict if MODE_HUMAN or
        MODE_AUTO_LOOP currently holds the lock exclusively."""
        if new_mode not in _SETTABLE_MODES:
            raise ValueError(f"not a settable mode: {new_mode!r}")
        with self._lock:
            if self._mode in _EXCLUSIVE_MODES:
                reason = "locked_by_human_attach" if self._mode == MODE_HUMAN else "locked_by_auto_loop"
                raise ControlModeConflict(reason)
            self._mode = new_mode
