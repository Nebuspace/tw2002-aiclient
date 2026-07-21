"""twclient/control_lock.py — the daemon's control-MODE state machine:
who is currently allowed to drive the ONE game connection.

Extensible mode enum, not a boolean (forward-compat seam for the
Trainer Control Panel, TUI-POLISH-PLAN.md's "Mode selector" --
{ai_pilot, auto_loop, human, spectate}):

  MODE_AI_PILOT (default) -- do/send/play/replay/haggle always succeed;
                   the AI drives. EXCLUSIVE-per-dispatch (TW-04): the AI
                   may drive, but only ONE do/send-family dispatch at a
                   time -- acquire_driver()/release_driver() (paired in
                   protocol.py's own dispatch-scoped guard, mirroring
                   take_human's discipline) reserve a single "active
                   driver" slot for the whole duration of one dispatch,
                   so two `tw do` calls racing in from separate one-shot
                   CLI connections (there's no persistent connection to
                   hold a lock across -- see DESIGN.md's one-shot-CLI
                   shape) can never both be mid-send at once. A second
                   concurrent driver is refused outright, never queued.
  MODE_HUMAN    -- an interactive `tw attach` session holds the keyboard;
                   every driving verb from anyone else is REJECTED
                   outright (never queued/interleaved onto the wire).
                   EXCLUSIVE + CONNECTION-SCOPED: only take_human()/
                   release_human() (always paired in one connection's
                   own try/finally -- see daemon.py's
                   CommandHandler._handle_attach) can enter/leave this
                   mode, so a crashed/killed attach session can never
                   wedge the daemon in it. A second take_human() while
                   one is already active is rejected. take_human()
                   itself always succeeds INSTANTLY even while an
                   ai_pilot dispatch is actively mid-flight (`_driving`)
                   -- the human always wins immediately, never blocked or
                   refused on that account -- but the dispatch caught
                   mid-flight is FENCED instead (WO-CLEANPREEMPT; see
                   take_human()'s own docstring for what that triggers).
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
    """Raised when a mode transition/reservation is rejected:
    take_human() finding MODE_HUMAN already held by another attach
    session, enter_auto_loop() finding MODE_HUMAN active OR an ai_pilot
    driver already mid-dispatch (TW-04 -- see acquire_driver()),
    acquire_driver() finding the active-driver slot already held by
    another dispatch OR the mode no longer `ai_pilot` (the P0 atomicity
    fix below -- same messages `protocol.py`'s `_control_lock_error`
    produces: `"controller_locked_by_human"`/`"controller_locked_by_
    auto_loop"`/`f"controller_locked:{mode}"`), or set_mode() finding
    MODE_HUMAN/MODE_AUTO_LOOP active (an attach's/loop's exclusive hold
    can't be clobbered by a plain mode-set)."""


class ControlLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._mode = MODE_AI_PILOT
        # TW-04: is some do/send-family dispatch (do/send/replay/play/
        # haggle) actively mid-flight right now? Orthogonal to `_mode`
        # (it's only ever True while _mode == MODE_AI_PILOT, since every
        # one of those verbs is already refused in any other mode -- see
        # protocol.py's _control_lock_error) but tracked separately
        # because "the AI may drive" (the mode) and "a specific driver
        # is driving THIS INSTANT" (this flag) are different questions --
        # see acquire_driver()/release_driver() below.
        self._driving = False
        # WO-CLEANPREEMPT (mack's TW-04-Axis-2 finding): does the
        # CURRENTLY-driving dispatch (if any) need to stop because
        # take_human() found `_driving` True and granted anyway instead
        # of refusing? Set only by take_human(), cleared only by
        # release_driver() (the fenced dispatch's own release) or a
        # fresh acquire_driver() claim -- never independently toggled
        # elsewhere. See take_human()/is_driver_fenced()'s docstrings.
        self._driver_fenced = False

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
        second attach.

        Never refuses -- or blocks -- purely because an ai_pilot dispatch
        is mid-flight (`self._driving`), unlike enter_auto_loop()'s
        symmetric `locked_by_active_driver` guard: the human always wins
        immediately (WO-CLEANPREEMPT). Instead, a driving dispatch caught
        mid-flight here is FENCED -- `_driver_fenced` flips True (read via
        is_driver_fenced()) -- so that dispatch's own caller
        (protocol.py's do/send/haggle, via `_driver_was_fenced()`) can
        flag its eventual ledger entry `interrupted_by_human`, and so
        `Session.send_raw()` can hold the human's own first keystroke off
        the wire until the fenced dispatch actually releases
        (release_driver() clears `_driving` and `_driver_fenced`
        together) -- a clean cutover onto the one wire, never a silent
        two-writer interleave, all without this call itself ever waiting
        on that release."""
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("already_attached")
            if self._mode == MODE_AUTO_LOOP:
                raise ControlModeConflict("locked_by_auto_loop")
            if self._driving:
                self._driver_fenced = True
            self._mode = MODE_HUMAN

    def release_human(self):
        """Idempotent -- always leaves MODE_AI_PILOT, even if called
        without a matching take_human() (defensive cleanup path)."""
        with self._lock:
            self._mode = MODE_AI_PILOT

    def is_driver_fenced(self):
        """True once take_human() has fenced an in-flight ai_pilot
        dispatch (see take_human()'s own docstring) -- cleared the
        moment that dispatch actually releases (release_driver()).
        Read by protocol.py's ledger hook (to flag
        `interrupted_by_human`) and by `Session.send_raw()` (to hold a
        human keystroke off the wire until the fence clears)."""
        with self._lock:
            return self._driver_fenced

    # -- exclusive, dispatch-scoped (TW-04: one in-flight ai_pilot driver) --

    def acquire_driver(self):
        """Reserves the single active-driver slot for the whole duration
        of one do/send-family dispatch (do/send/replay/play/haggle --
        see protocol.py's shared `_driving_dispatch` guard). Two `tw do`
        calls racing in from separate one-shot CLI connections both pass
        `ai_may_send()` (mode == ai_pilot is true for either); without
        this second, EXCLUSIVE layer on top, both could call
        `session.send()` around the same moment and interleave two
        different logical conversations onto the one wire -- individual
        `Session.send()` calls are already byte-atomic (session.py's own
        `send_lock`), but nothing serialized the SEMANTIC send-then-
        settle unit until now.

        **Atomicity fix (P0):** `_control_lock_error`'s mode check and
        this method used to be two SEPARATE lock acquisitions --
        `protocol.py`'s `_driving_dispatch` calls the former, sees mode
        == ai_pilot, then calls this method a moment later. In that
        window, `enter_auto_loop()`/`take_human()` could slip in, flip
        the mode away from ai_pilot, and this method would never
        re-check it -- only `self._driving`. A `do`-family dispatch
        could then win the driver slot while AUTO-LOOP or a human attach
        believed it held exclusive control, interleaving two independent
        send-then-settle units onto the one wire (the exact class TW-04
        exists to prevent, just one layer up). This method is now the
        single atomic authority: mode AND the driver slot are checked
        (and the slot claimed) under ONE lock hold, so nothing can
        interleave between them. `_control_lock_error`'s own separate
        check stays in place purely as a fast, clear up-front error for
        the common (non-racing) case -- it is never the source of truth.

        Raises `ControlModeConflict` naming WHY: mode-refusal first
        (`"controller_locked_by_human"` / `"controller_locked_by_
        auto_loop"` / `f"controller_locked:{mode}"` -- identical strings
        to `_control_lock_error`'s, so a caller can't tell which check
        caught it), else `"controller_busy"` if the slot itself is
        already held. Refused outright, never queued (queuing would mean
        holding a second client's one-shot socket open indefinitely,
        which this protocol was never built to do). Always paired with
        release_driver() in the caller's own try/finally -- crash-safe
        like take_human()/release_human()."""
        with self._lock:
            if self._mode != MODE_AI_PILOT:
                if self._mode == MODE_HUMAN:
                    raise ControlModeConflict("controller_locked_by_human")
                if self._mode == MODE_AUTO_LOOP:
                    raise ControlModeConflict("controller_locked_by_auto_loop")
                raise ControlModeConflict(f"controller_locked:{self._mode}")
            if self._driving:
                raise ControlModeConflict("controller_busy")
            self._driving = True
            # WO-CLEANPREEMPT: a fresh claim always starts unfenced --
            # release_driver() already clears this on the way out of the
            # PREVIOUS hold, so this is belt-and-suspenders defensive
            # (matching this method's own "single atomic authority"
            # discipline) rather than a case that should ever fire live.
            self._driver_fenced = False

    def release_driver(self):
        """Idempotent -- safe even if acquire_driver() was never called
        (defensive cleanup path), mirroring release_human(). Also clears
        `_driver_fenced` (WO-CLEANPREEMPT): a fence is scoped to the ONE
        dispatch that was caught mid-flight -- once it releases, mode is
        already MODE_HUMAN, so no NEW ai_pilot dispatch can acquire the
        driver slot to re-fence it (acquire_driver()'s own mode check
        refuses outright), and nothing is left for a human keystroke to
        wait on."""
        with self._lock:
            self._driving = False
            self._driver_fenced = False

    def is_driving(self):
        """True while the active-driver slot is held (some do/send-
        family dispatch is mid-flight right now). Read by
        `_dispatch_play_start` (protocol.py) so an AUTO-LOOP start
        request can refuse up front, with a clear error, instead of
        racing enter_auto_loop() below for the answer."""
        with self._lock:
            return self._driving

    # -- exclusive, thread-scoped (loop_player.LoopPlayer) ----------------

    def enter_auto_loop(self):
        """Entered only via LoopPlayer.start() (never the generic
        set_mode() verb -- see module docstring). Refuses to preempt an
        active human attach, mirroring take_human()'s own no-stealing
        rule in the other direction -- and (TW-04) refuses to preempt an
        ai_pilot dispatch that's actively mid-flight RIGHT NOW, the same
        no-stealing rule extended to the active-driver slot. This check
        happens atomically under the same lock as the mode transition
        (not as a separate up-front look-then-act in protocol.py) so a
        `do` dispatch starting in the instant between a caller's check
        and this call can never still get silently preempted."""
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("locked_by_human_attach")
            if self._mode == MODE_AUTO_LOOP:
                raise ControlModeConflict("already_running")
            if self._driving:
                raise ControlModeConflict("locked_by_active_driver")
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
