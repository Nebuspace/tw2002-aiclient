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

**TW-03/TW-04:** every cycle drives `replay_skill()` directly (not
`skills.play_skill()` -- this module already has its own cycle/floor
loop), so it inherits both fixes from there for free as long as this
module forwards the right arguments: the TW-03 start-anchor guard (an
AUTO-LOOP run that wanders off its recorded start sector halts exactly
like any other mid-run surprise) and the TW-04 Trace-Ledger row per
send (`ledger`/`session_id`, optional constructor args, `actor="trainer"`
-- see `skills.replay_skill`'s docstring for the full contract).

**WO-CLEANPREEMPT:** `_run()` also forwards `is_driver_fenced` into every
`replay_skill()` call, same as `_dispatch_replay`/`_dispatch_play`
(protocol.py) do -- currently a no-op for this caller specifically (see
`_run()`'s own comment: take_human() already refuses outright while
MODE_AUTO_LOOP is active, so the driver slot can never be fenced during
an AUTO-LOOP run in the first place), wired for consistency/future-
proofing rather than because a live gap exists here today. `ReplayFenced`
is still caught defensively (`last_result = "human_fenced"`) so a future
change to that invariant can't crash this background thread uncaught.

**WO-FA-SAFE (hub-signed-off design + Rook architecture-approved): the
credit-floor stop-loss now reads the STRICT last-known balance, never the
loose one.** The pre-cycle floor-check below used to read
`snapshot_state(text).get("credits")` -- `state_parser.parse_state()`'s
looser, price-pollutable `credits` field, which a port's own price quote
satisfies just as well as a real balance (and fails OPEN, proceeding, on
`None`). It now reads `session.credits_snapshot()` -- the SAME
`last_credits`/`last_credits_ts` pair `observe_credits()` maintains (see
session.py) -- and is fail-CLOSED: HALTs (`"credits_unknown"`) whenever
the balance was never observed or is older than `self.caps.
credits_stale_ms` (default 15s, an `EconCaps` field -- see `start()`'s own
`caps=` param), and only proceeds on a FRESH, confirmed balance strictly
greater than `self.floor`. This closes the "a stale-but-still->floor
screen reading masks a real sub-floor balance" defeat a loose/fail-open
read could not.

Bounded exposure (Rook must-fix #4): the 15s default trusts ONE balance
reading across a whole macro-cycle's worth of spends -- it can predate
the cycle's own last buy. This is a TIME backstop, not per-spend
precision; a genuinely per-spend "confirmed since the last buy" gate is
FA4's buy-flow's own job (flagged for the hub), not this loop's.

Honesty note (mack LOW a, hub-ratified revise item 4): `start()`'s
`caps=` param means a Python-API caller CAN override `credits_stale_ms`
per-run with no rebuild -- but unlike `autopilot.py`'s arm path
(`tw autopilot start --credits-stale-ms`, protocol.py's
`_dispatch_autopilot_start`), THIS module has no CLI/dispatch-level
flag of its own yet (`tw play`/`tw play_start` have no
`--credits-stale-ms`) -- every real caller through those verbs gets the
15s default. Don't describe this path as "supervisor-tunable live"; that
claim only holds for the autopilot arm path today. CLI threading here is
a deferred follow-on, not built by this revise.

Startup precondition (Rook must-fix #5): a run whose `floor` is set HALTS
on cycle 0 with `"credits_unknown"` if no balance was EVER observed before
`start()` -- the arm sequence (crawl login/dock) must have shown a
confirmed balance first, or a legitimate run instant-dies. This is the
honest fail-closed signal, not a bug to work around with a fake seed
balance.

Multiplayer arming-gate (Rook must-fix #6, written, not a footnote): this
stop-loss inherits `credits_balance()`'s documented FORGED-BALANCE
residual (state_parser.py, FA9-class roadmap prerequisite) -- a forged
in-band "You have N credits" broadcast poisons `last_credits` exactly like
a real one. SOLO-safe today (no other player exists on a crawl_sacrificial
game to author such a forgery); **arming this stop-loss in multiplayer
REQUIRES WO-FA9 first.**

Rook must-fix #2 (chain candidates, autopilot.py sibling site): `_score_
chain()` never reads `snapshot.credits` at all -- see that function's own
comment for why a stale/unknown balance does NOT gate a `run_chain`
candidate today, and what that depends on staying true.
"""

import threading
import time

from .autopilot import EconCaps
from .control_lock import ControlModeConflict
from .skills import ReplayDivergence, ReplayFenced, SkillError, replay_skill

_PAUSE_POLL_S = 0.1

# This repo's hard-cap ethos (see skills.py's own _MAX_PLAY_CYCLES)
# applied independently here -- an unattended AUTO-LOOP background
# thread cannot be armed for more than this regardless of caller intent.
_MAX_CYCLES = 50


class LoopPlayerError(Exception):
    """A start/pause/resume/stop request that doesn't apply to the
    player's current state (e.g. starting while already running)."""


class LoopPlayer:
    def __init__(self, session, control_lock, watch_hub, ledger=None, session_id=None):
        self.session = session
        self.control_lock = control_lock
        self.watch_hub = watch_hub
        # TW-04: optional ledger.LedgerWriter-shaped object + the
        # session_id every ledger row this player produces gets tagged
        # with (actor="trainer" is hardcoded at the call site below --
        # an AUTO-LOOP run is deterministic-engine-driven by definition).
        # Both None by default -- a caller that hasn't wired them up yet
        # (e.g. a bare dispatch-harness test) keeps behaving unchanged.
        self.ledger = ledger
        self.session_id = session_id
        self._state_lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self.skill_name = None
        self.cycles_total = 0
        self.cycles_done = 0
        self.floor = None
        # WO-FA-SAFE: the stop-loss's freshness bound (`caps.
        # credits_stale_ms`) -- a real `EconCaps()` default here so
        # `self.caps` is always a valid object even before the first
        # `start()` call; `start()`'s own `caps=` param overrides it
        # per-run (see that method's docstring).
        self.caps = EconCaps()
        self.last_result = None  # None while running; else "cycles_complete" | "surprise" | "floor_reached" | "credits_unknown" | "stopped" | "refused" | "human_fenced"
        self.last_error = None  # str(exc) when last_result == "refused" (TW-03: e.g. a missing start_anchor); else None

    @property
    def running(self):
        with self._state_lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self):
        return self._pause.is_set()

    def start(self, skill, name, cycles, floor=None, params=None, step_timeout=8.0, force=False, caps=None):
        """Raises LoopPlayerError if a run is already active or `cycles`
        exceeds the hard cap, ControlModeConflict if the control-lock
        refuses (human attached, or -- belt and suspenders -- somehow
        already in auto_loop). `force` (TW-03) is forwarded to every
        cycle's `replay_skill()` call -- it waives ONLY a missing/legacy
        `start_anchor` on `skill`, never a detected sector mismatch; see
        `skills._check_start_anchor()`.

        `caps` (WO-FA-SAFE, optional `autopilot.EconCaps`): only its
        `credits_stale_ms` field is consulted, by the floor-check below --
        defaults to `EconCaps()` (15s) when omitted, same config object the
        `autopilot.py` decision site reads, so a caller tuning the
        stop-loss's freshness bound has one knob, not two independently-
        drifting ones. A run with no `floor` set never reads it at all.

        STARTUP PRECONDITION (Rook must-fix #5): if `floor` is set, cycle 0
        HALTs with `last_result="credits_unknown"` unless a confirmed
        balance was already observed on this session (via
        `session.observe_credits()`, e.g. during the arm sequence's own
        crawl login/dock screen) before this call -- see module docstring."""
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
            self.caps = caps if caps is not None else EconCaps()
            self.last_result = None
            self.last_error = None
            self._stop.clear()
            self._pause.clear()
            self._thread = threading.Thread(
                target=self._run, args=(skill, params or {}, step_timeout, force), daemon=True
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
            "last_error": self.last_error,
        }

    def _run(self, skill, params, step_timeout, force=False):
        result = "cycles_complete"
        error_msg = None
        try:
            for cycle in range(self.cycles_total):
                while self._pause.is_set() and not self._stop.is_set():
                    time.sleep(_PAUSE_POLL_S)
                if self._stop.is_set():
                    result = "stopped"
                    break
                if self.floor is not None:
                    text = self.session.render_text(self.session.render())
                    # WO-FA7a round 4: feed the credits-supervision surface
                    # from THIS render too -- it's the single most
                    # supervision-relevant screen this loop ever produces,
                    # since a `floor_reached`/`credits_unknown` break exits
                    # right here, on cycle 0 if the floor is already
                    # crossed, NEVER reaching replay_skill's own per-step
                    # capture at all. hasattr-guarded, mirroring every other
                    # call site (session.py/protocol.py/skills.py/
                    # crawl_driver.py).
                    if hasattr(self.session, "observe_credits"):
                        self.session.observe_credits(text)
                    # WO-FA-SAFE (hub-signed-off design + Rook must-fix #3):
                    # the STRICT last-known-balance stop-loss -- replaces
                    # the loose `snapshot_state(text).get("credits")` read
                    # this line used to make (`state_parser.parse_state()`'s
                    # own price-pollutable `credits` field, which a port's
                    # own price quote satisfies just as well as a real
                    # balance, and which failed OPEN -- proceeding -- on
                    # `None`). `credits_snapshot()` is an ATOMIC read
                    # (session.py) of the SAME `last_credits`/
                    # `last_credits_ts` pair `observe_credits()` just wrote
                    # above, from THIS render -- as fresh as this cycle can
                    # get. hasattr-guarded the same way: a session lacking
                    # `credits_snapshot()` entirely reads as `(None, None)`,
                    # the same fail-closed shape as a real session that
                    # never captured a balance. See this module's own
                    # docstring for the 15s freshness-bound exposure, the
                    # cycle-0 startup precondition, and the FA9 multiplayer
                    # arming-gate this stop-loss inherits.
                    if hasattr(self.session, "credits_snapshot"):
                        bal, ts = self.session.credits_snapshot()
                    else:
                        bal, ts = None, None
                    age_ms = (time.monotonic() - ts) * 1000 if ts is not None else None
                    fresh = bal is not None and age_ms is not None and age_ms <= self.caps.credits_stale_ms
                    if not fresh:
                        # Fail-CLOSED: unknown (never observed) or stale
                        # (older than credits_stale_ms) -- never assume a
                        # sub-floor balance is safe just because we can't
                        # currently confirm it.
                        result = "credits_unknown"
                        break
                    elif bal <= self.floor:
                        result = "floor_reached"
                        break
                try:
                    replay_skill(
                        self.session,
                        skill,
                        params=params,
                        step_timeout=step_timeout,
                        force=force,
                        ledger=self.ledger,
                        session_id=self.session_id,
                        # WO-CLEANPREEMPT: threaded through for consistency
                        # with every other replay_skill() caller, though
                        # currently provably inert for THIS caller --
                        # take_human() refuses outright while MODE_AUTO_LOOP
                        # is active (`locked_by_auto_loop`, control_lock.py),
                        # so `_driving` (the only thing take_human() fences
                        # on) can never be True while this loop is running:
                        # acquire_driver() itself refuses the instant mode
                        # isn't ai_pilot. Kept wired anyway so a future
                        # change to that invariant doesn't silently leave
                        # this caller unprotected.
                        is_driver_fenced=self.control_lock.is_driver_fenced,
                    )
                except ReplayFenced:
                    result = "human_fenced"
                    break
                except ReplayDivergence:
                    result = "surprise"
                    break
                except SkillError as e:
                    # TW-03: a missing/legacy start_anchor refused without
                    # force=True (see skills._check_start_anchor()) -- a
                    # config-level refusal, not a live "surprise", but
                    # still needs to end this cycle's run cleanly rather
                    # than escape uncaught out of a background thread
                    # (which would leave last_result stuck at whatever it
                    # defaulted to, silently misreporting what happened).
                    result = "refused"
                    error_msg = str(e)
                    break
                self.cycles_done = cycle + 1
                self._broadcast_progress()
        finally:
            self.last_result = result
            self.last_error = error_msg
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
