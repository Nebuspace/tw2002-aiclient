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
                         an in-flight App dispatch, OR an in-flight auto_loop
                         hold — either is FENCED, not refused, and neither is
                         merely revoked silently). A second take_human() while
                         already attached raises ``already_attached``.
  MODE_SPECTATE       -- paused / read-only standing state. Nobody may acquire
                         the driver slot (typed ``spectate_read_only``).

auto_loop is not a mode string: enter_auto_loop() / leave_auto_loop() mark an
exclusive App hold while ``mode`` stays ``app``. set_mode() cannot enter or
clobber that hold, and cannot enter MODE_HUMAN (attach-scoped only).

WO-CONTROL-LOCK-AUTOLOOP-FENCE: take_human() preempting a dispatch and
take_human() preempting an auto_loop hold used to get two different
treatments -- a dispatch was fenced (``is_driver_fenced()`` stayed True
until ``release_driver()``), an auto_loop hold was just silently revoked
(``_auto_loop_held`` -> False, no fence raised at all). The gap mattered
because ``Session.send_raw``'s bounded wind-down wait -- its only caller is
the daemon's human-attach keystroke forwarder -- polls ``is_driver_fenced()``
before letting a human byte reach the wire. A dispatch fence gave the
human's own first keystrokes a beat to let the in-flight App step actually
finish; an auto_loop preemption gave them none, so a human's attach bytes
could race a loop step still winding down between boundary checks. Fixed
by raising the SAME signal for both preemptions: an auto_loop preemption
now also feeds ``is_driver_fenced()``, kept independent of the dispatch
path's own ``_driver_fenced`` (never a shared flag between the two
SOURCES) because both release paths are idempotent and run on every
completion -- sharing one would let whichever ran first clear a signal it
never raised. The LoopPlayer's own halt decision was never the gap -- it
already re-reads its own hold via ``is_auto_loop_held()`` (see
``session/autoloop.py``'s port) -- this closes the human-keystroke side,
which had no wind-down courtesy at all.

That answers "can the dispatch fence and the auto_loop fence cross-clear
each other" (no), but it does NOT by itself answer a harder question: can
a hold OUTLIVE the run that took it, so that a caller three runs later is
still able to touch it?

**It cannot, and that took a second mechanism.** ``_auto_loop_held`` is
cleared IMMEDIATELY by ``take_human()`` (unlike ``_driving``, which stays
busy -- refusing every new ``acquire_driver()`` -- for the entire fenced
window, until the SAME dispatch's own ``release_driver()``). Nothing
stops a FRESH ``enter_auto_loop()`` from succeeding the moment a human
detaches, while the PREEMPTED run's own thread is still winding down and
will eventually call ``leave_auto_loop()`` itself. Reproduced against the
real class: run A enters, a human preempts it and detaches, run B enters
fresh, and A's own stale release -- arriving late, e.g. a wedged settle
wait finally returning -- has nothing in the object to tell it that the
hold it is about to touch is not the one it took. An unconditional
release (clear the hold, clear the fence, regardless of caller) would let
A's stale call destroy B's hold -- two drivers on one wire, the exact
hazard the hold exists to prevent -- and, if B was ALSO mid-preemption at
that moment, would flip B's own genuine fence True -> False out from
under it, reopening the exact TOCTOU this WO exists to close, via an
unrelated stale caller.

**The hold** is fixed with a **generation token**: ``enter_auto_loop()``
mints one (an opaque, monotonically increasing int) and returns it;
``leave_auto_loop()`` takes one back and only releases ``_auto_loop_held``
when handed the CURRENT generation. A caller with no token (the default)
or a superseded one can never release a hold that was never its own,
regardless of how ``_auto_loop_held`` happens to read at that moment.

**The token is a no-op guard on stale releases, not a reclaim mechanism
for new holders -- and that distinction is load-bearing.** A tempting
reading of "generation token" is *newest wins*: a fresh
``enter_auto_loop()`` supersedes and clears whatever the previous
generation left behind, including its fence obligations. That is wrong,
and wrong in the SAME direction as the bug this fix closes, merely run
the other way: it would let a NEW generation silently erase a claim an
OLDER one still legitimately owns -- e.g. a wedged run genuinely still
blocked inside a blocking ``sendall()`` (``connection.py``; tracked
separately as ``WO-WEDGED-SEND-FENCE-STICKS``, and this fix must not
touch that severity in either direction). So ``enter_auto_loop()`` never
touches an existing fence obligation on grant -- whatever a predecessor
still owes stays exactly as owed.

**The fence is not "a flag" at all -- it is a SET of generations that
each still owe a wind-down**, and every attempt to represent it as
anything smaller (a bool; a bool plus one owner slot) reproduced the same
defect somewhere else, three times, on the same day:

1. A single bool with no owner at all: a stale release from ANY
   generation could clear it, including one that never raised it.
2. A bool plus ONE owner slot (round 3, "did `generation` raise it"): closed
   (1), but a SECOND preemption -- a different generation, ALSO fenced
   before the first released -- has nowhere to go but overwrite the same
   slot, and the first generation's claim is gone, not merely
   unreachable. Reproduced against the real class: A enters, is preempted
   and wedged (fenced); B enters, is ALSO preempted and wedged (fenced,
   overwriting A's stamp); B releases its OWN claim; the flag reads
   unfenced with A still wedged on the wire.

Both are the identical mistake at different cardinalities: **the model
being represented is "the set of generations owed a release," and a
scalar -- with or without a single owner tag -- cannot hold a set.**
``_auto_loop_fenced_generations`` is that set, directly: ``take_human()``
**adds** the generation it preempts (alongside whatever is already
outstanding, never instead of it); ``leave_auto_loop(generation)``
**discards** exactly that one. Set membership doubles as the ownership
check for free -- discarding a value that was never added (a
never-preempted generation's own clean exit; any stale or unrelated
token) is already the correct no-op, with no second comparison to write
or get wrong. Two generations independently outstanding now survive
independently: whichever releases first removes only itself, and the
other's claim -- and whatever it may still be doing on the shared wire --
is untouched, no matter how many more releases or fresh grants happen in
between.

**What this set does NOT claim: that production ever actually populates it
past one member.** This class's OWN contract permits arbitrarily many
outstanding generations -- that permissiveness is the whole point of the
fix above -- but nothing IN THIS CLASS pins "at most one generation is
ever outstanding at a time" as a standing invariant. Today that bound
holds only because of an EXTERNAL caller's discipline:
``session/autoloop.py``'s ``AutoLoopRunner`` never lets a second
``enter_auto_loop()`` be attempted while an earlier run's thread has not
yet reached its own release (`_in_flight` refuses a second `start()`
first). Verified empirically, not assumed: the >1 case is unreachable
THROUGH THAT CALLER today, which is a fact about the caller's
bookkeeping, not a fact this class enforces or could detect a violation
of on its own. A second call site, a loosened one-runner-per-daemon
discipline, or any other caller of ``enter_auto_loop()`` added later
would find this class fully willing to track two, three, or more
outstanding generations without complaint -- which is correct FOR THIS
CLASS (a lock must not assume its own caller's discipline), but is
precisely why ``AutoLoopRunner.start()`` carries its own loud, explicit
assertion of that external invariant (see its docstring) rather than
leaving it to be merely true by construction of code nobody has pinned.
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
        # WO-CONTROL-LOCK-AUTOLOOP-FENCE (Mack's CRITICAL): identifies WHICH
        # hold `_auto_loop_held` currently belongs to. Bumped by every
        # enter_auto_loop() grant; leave_auto_loop() must be handed the
        # SAME value back to release the HOLD — see the module docstring's
        # generation-token section. (The fence has its own, separate
        # membership test — see `_auto_loop_fenced_generations` below.)
        self._auto_loop_generation = 0
        # Active do/send-family dispatch slot (orthogonal to mode; only
        # claimable while mode == MODE_APP and not auto_loop-held).
        self._driving = False
        # WO-CLEANPREEMPT: take_human() found an in-flight App dispatch and
        # granted anyway — fence it so Session.send_raw can hold the human's
        # first keystroke off the wire until release_driver().
        self._driver_fenced = False
        # WO-CONTROL-LOCK-AUTOLOOP-FENCE (round 4): the SET of generations
        # that still owe a wind-down -- not a bool, not a bool-plus-one-
        # owner-slot. What this represents is "who still owes a release",
        # and more than one generation can owe one at once (each preempted
        # in turn while the previous had not yet released) -- a single
        # flag or a single owner slot can only ever remember the LAST
        # claim, silently forgetting an earlier one the moment a second is
        # raised. Membership IS ownership: `take_human()` adds the
        # generation it preempts, `leave_auto_loop(generation)` discards
        # exactly that one (a `set.discard` on a non-member, or a value
        # nobody ever added, is already a no-op — the right behaviour for
        # a stale or non-owning caller, for free). Kept as its own
        # collection rather than folded into `_driver_fenced` because its
        # release path is different — `leave_auto_loop()`, not
        # `release_driver()`.
        self._auto_loop_fenced_generations = set()

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
        (``already_attached``). Never blocks and never denies the human —
        only delays a byte, and only by a bounded courtesy wait one layer
        up (``Session.send_raw``). Whichever exclusive App hold is
        mid-flight, dispatch or auto_loop, is FENCED here rather than
        merely cleared: ``_driving`` fences ``is_driver_fenced`` until
        ``release_driver()``, and an active ``_auto_loop_held`` adds the
        generation being preempted to ``_auto_loop_fenced_generations``
        until ``leave_auto_loop()`` discards it — so ``Session.send_raw``'s
        wind-down wait sees the same signal either way, and a human's
        first keystrokes get the same beat to let an in-flight loop step
        actually finish that a dispatch already got. If a DIFFERENT
        generation is already in the set from an earlier, still-unreleased
        preemption, this one is added alongside it, not instead of it —
        both are outstanding, and both must independently be released.
        This class permits it; whether anything in the daemon can ever
        actually DRIVE it to more than one member is a fact about the
        caller, not this method — see the module docstring's closing note.
        """
        with self._lock:
            if self._mode == MODE_HUMAN:
                raise ControlModeConflict("already_attached")
            if self._driving:
                self._driver_fenced = True
            if self._auto_loop_held:
                self._auto_loop_fenced_generations.add(self._auto_loop_generation)
            self._auto_loop_held = False
            self._mode = MODE_HUMAN

    def release_human(self):
        """Idempotent — always returns to MODE_APP (defensive cleanup).

        Deliberately does NOT touch `_auto_loop_fenced_generations`: every
        generation still in that set is this method's to leave alone, not
        to launder. Each is discarded only by ITS OWN matching
        `leave_auto_loop(generation)`, whenever it finally arrives — never
        by this method, and never by a LATER `enter_auto_loop()` either
        (that would be the "newest wins" trap the module docstring's
        generation-token section warns against). A caller three attaches
        later still seeing `is_driver_fenced()` True because one or more
        EARLIER generations never released is correct, not a bug: each of
        those predecessors' wind-downs may still be genuinely in flight on
        the one shared wire.
        """
        with self._lock:
            self._mode = MODE_APP
            # Attach release never invents an auto_loop hold.
            self._auto_loop_held = False

    def is_driver_fenced(self):
        """Duck-typed by Session.send_raw — True while EITHER a fenced
        dispatch (``_driving``, cleared by ``release_driver()``) OR ANY
        auto_loop generation still owes a wind-down (a non-empty
        ``_auto_loop_fenced_generations``, each member cleared
        independently by its own ``leave_auto_loop(generation)``). One
        honest signal for the one caller that waits on it — see the module
        docstring's WO-CONTROL-LOCK-AUTOLOOP-FENCE note for why these used
        to disagree, and for why the auto_loop half is a SET rather than a
        single flag."""
        with self._lock:
            return self._driver_fenced or bool(self._auto_loop_fenced_generations)

    def outstanding_auto_loop_generations(self):
        """A read-only SNAPSHOT of which generations still owe a wind-down
        (a ``frozenset`` copy — never the live set, so a caller can never
        mutate this class's own bookkeeping by holding onto the return
        value). This class's contract permits any number of members; it is
        the caller's job to decide what number it considers acceptable
        (``AutoLoopRunner.start()`` asserts it never sees more than zero
        before granting a new one — see that method's own docstring, and
        the module docstring's closing note on why that assertion lives
        THERE and not in this class)."""
        with self._lock:
            return frozenset(self._auto_loop_fenced_generations)

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

        Returns a **generation token** (an opaque, monotonically
        increasing ``int``) identifying THIS hold. The caller must hold
        onto it for the lifetime of its run and hand it back to
        `leave_auto_loop()` when releasing — never share it, never guess
        it, never reuse an old one. See the module docstring's
        generation-token section for why: a caller with no token, or a
        superseded one, must not be able to touch a hold or fence that
        was never its own.

        Deliberately does **not** touch `_auto_loop_fenced_generations` on
        grant — see the module docstring's "no-op guard, not a reclaim
        mechanism" note. Whatever generations still owe a wind-down from
        BEFORE this grant stay exactly as outstanding as they were; this
        one simply is not among them yet (it is only added later, by its
        own `take_human()` preemption, if any). A fresh generation must
        not silently erase a predecessor's still-genuine claim, which is
        the "newest wins" trap this WO exists to avoid, not reintroduce in
        the other direction.
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
            self._auto_loop_generation += 1
            return self._auto_loop_generation

    def leave_auto_loop(self, generation=None):
        """Releases the hold and discards this generation's fence claim —
        two independent operations, because a generation can be current
        for one and a member of the other, in any combination:

        * **the hold** releases iff `generation` equals the CURRENT
          `_auto_loop_generation`. This is the fix for Mack's original
          CRITICAL, reproduced against the real class: run A enters, a
          human preempts it and detaches, run B enters fresh, and A's own
          stale release — arriving late — must not touch B's hold. A
          no-op if there is no token at all (the default `None`, for a
          caller that never entered) or a stale one a later
          `enter_auto_loop()` has already superseded.
        * **the fence** discards `generation` from
          `_auto_loop_fenced_generations` — a `set.discard`, which is
          ALREADY a no-op for a value that was never a member (a caller
          that was never preempted, or a fully-unrelated token). This is
          what makes ownership need no separate comparison: membership
          IS ownership. A generation that inherits a predecessor's still-
          outstanding claim (by design — see `enter_auto_loop()`) is not
          itself a member, so its own clean release discards nothing and
          the predecessor's claim survives untouched — and if TWO
          generations are independently outstanding (each preempted while
          the previous had not yet released — Cipher's round-4 finding:
          a single owner slot can only remember the LAST one), one's
          release still only discards its own membership, leaving the
          other's claim exactly as outstanding as before. Reachable
          against this bare class in a unit test; NOT reachable through
          `AutoLoopRunner` today (see the module docstring's closing
          note) — this method still has to be correct for it regardless,
          because that reachability is the caller's property, not this
          class's.

        Both operations are independent and typically both act on the
        same call (the ordinary case: a generation releasing its own hold,
        having raised its own fence, clears both at once) or only one may
        (a current-but-never-preempted generation's clean exit; a
        no-longer-current generation finally releasing the claim it
        raised) or neither may (a totally unrelated/stale token). Never
        clobbers a DIFFERENT mode (e.g. a human attach that landed while
        the loop was finishing) — this method never touches `mode`.

        Called from the run's own release path — normally its `finally`
        as it dies (per `session/autoloop.py`'s module docstring), or
        `start()`'s own unwind if the thread never even got running.
        """
        with self._lock:
            if generation == self._auto_loop_generation:
                self._auto_loop_held = False
            self._auto_loop_fenced_generations.discard(generation)

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
