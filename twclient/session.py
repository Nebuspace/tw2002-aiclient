"""Session — the live telnet+pyte state a daemon process owns.

Implements the settle-detection protocol (`.rx_count`, `.last_rx`,
`.clock()`, `.sleep()`, `.render_text()`) directly, so `settle.wait_for_settle`
can be handed `self`.
"""

import threading
import time

from .classify import is_probable_secret_prompt
from .connection import TelnetConnection
from .iac import TelnetHandler
from .logging_util import TranscriptLogger
from .settle import wait_for_settle
from .state_parser import credits_balance
from .terminal import TerminalScreen

MIN_SEND_GAP_S = 0.15  # guardrail: no hammering the server

# WO-CLEANPREEMPT: bounded wait for a FENCED in-flight ai_pilot dispatch
# to actually release before a human `tw attach` keystroke reaches the
# wire (see Session.send_raw()'s own docstring). Generous relative to
# `do`'s own default settle timeout (protocol.py's "timeout" arg, 8.0s)
# so an ordinary in-flight dispatch clears well within it; a genuinely
# wedged dispatch (one that never reaches `release_driver()` at all --
# which would already violate every OTHER try/finally-paired guarantee
# in this codebase) is the only way this bound is ever actually reached,
# and even then this is a courtesy ORDERING wait, never a second refusal
# path -- the keystroke is sent regardless once the bound expires.
_FENCE_WAIT_TIMEOUT_S = 10.0
_FENCE_WAIT_POLL_S = 0.02


class Session:
    def __init__(self, host, port, name, log_dir):
        self.host = host
        self.port = port
        self.name = name

        self.terminal = TerminalScreen()
        self.negotiator = TelnetHandler()
        self.logger = TranscriptLogger(log_dir)
        self.conn = TelnetConnection(self.host, self.port, self.terminal, self.negotiator, logger=self.logger)

        self.lock = self.conn.lock
        self.send_lock = threading.Lock()
        self._last_send_time = 0.0

        # TX channel (TUI-POLISH-PLAN.md "Core transparency"): the most
        # recent thing sent to the game, threaded through
        # protocol.build_response() so every watch event -- AI-pilot,
        # auto-loop, or attach alike -- can show it, from ONE chokepoint
        # (send()/send_raw() below), the same way build_response() is
        # the single chokepoint on the receive side. `None` until the
        # first send; a `secret=True` send() -- and, as of WO-CLEANPREEMPT's
        # secret sub-diff, a secret-prompt send_raw() attach keystroke too
        # -- stores the SAME "<redacted>" placeholder protocol.py's
        # history/ledger already use -- never the real password text.
        # This closes the THIRD sink (`tw status`'s `sent_input` field,
        # which reads straight off this attribute, and therefore the
        # spectate TX-channel display that reads `sent_input` too) with
        # the SAME send-time `secret` reading send_raw() already computes
        # for the LOG/LEDGER sinks -- one decision, three sinks now, never
        # a separate derivation for this one.
        self.last_sent = None
        self.last_sent_ts = None
        # WO-CLEANPREEMPT (secret sub-diff): send_raw()'s OWN send-time
        # secret decision (is_probable_secret_prompt() against the
        # CURRENT screen, evaluated right before the byte reaches the
        # wire -- see send_raw()'s docstring), exposed here so daemon.py's
        # CommandHandler._handle_attach can read the SAME decision back
        # after the call and thread it into protocol.record_attach_
        # keystroke()'s own ledger row, rather than re-deriving it a
        # second, potentially-stale way. `send()`'s own `secret` argument
        # is caller-supplied and unrelated to this -- this attribute is
        # ONLY ever set by send_raw(), defaulting False until the first
        # attach keystroke.
        self.last_sent_secret = False

        # RX-side counterpart to last_sent/last_sent_ts above (WO-FA7a,
        # credits-supervision surface): the most recent STRICT credits
        # balance `observe_credits()` (below) found on any settled screen,
        # so `tw status` can serve a passive "last known credits" reading
        # to a polling caller (the E2 supervised-run hub, WO-FA7b) with
        # zero new network I/O -- no polling send of its own, ever.
        # Mirrors last_sent/last_sent_ts's field shape exactly: `None`
        # until the first credits-bearing screen. Set ONLY by
        # `observe_credits()`, never here directly (mirrors how
        # last_sent/last_sent_ts are only ever written by send()/
        # send_raw() above, not by __init__ again later) -- and, unlike
        # last_sent, deliberately NEVER cleared by a later screen with no
        # balance line, so a caller always sees the last genuine reading
        # (with its own, correspondingly stale ts) rather than it
        # vanishing. Credits are not secret -- this never goes near
        # log_redacted() or either of the other two redaction sinks
        # (ledger/last_sent) above.
        self.last_credits = None
        self.last_credits_ts = None

        self.history = []  # ring buffer of recent do/read events
        self._history_cap = 200

        # D9 reconnect + login-replay: set once `ensure` succeeds against
        # a profile, so a later drop can be auto-recovered without the
        # caller re-specifying which credential to replay.
        self.auto_login_profile = None

        # Safety fix: once login.py has genuinely CLEARED the real game-
        # select screen on this TCP connection (sent the configured letter
        # AND a later classification is no longer `game_select`), it
        # refuses to send `profile.game_letter` again -- closing the
        # `ensure`-mid-session stale-pyte-buffer misfire vector at the
        # SOURCE (a stale game-select header/marker left over from earlier
        # in the connection, plus a later ordinary screen sharing the same
        # generic prompt, could otherwise get misclassified as game_select
        # and re-answered with a blind keystroke) -- independent of any
        # classify.py heuristic. NOT latched on send-confirm alone: a
        # false-positive idle settle that leaves the CURRENT screen still
        # classified as `game_select` must remain retryable. PER-
        # CONNECTION, not per-login-run: reset below in reconnect() so a
        # genuinely fresh connection (guardian's D9 reconnect-replay, or a
        # fresh cold-start login) can still answer game-select normally.
        self.game_select_answered = False
        # Set True the first time login.py sends `profile.game_letter` on
        # this connection; used with `game_select_answered` above to know
        # a non-`game_select` classification means we cleared, not skipped.
        self.game_select_letter_sent = False

    def start(self, timeout=10):
        self.conn.connect(timeout=timeout)

    def mark_profile(self, profile_name):
        """Record which profile last successfully logged this session in
        -- the SessionGuardian (D9) replays login against this profile
        after an auto-reconnect."""
        self.auto_login_profile = profile_name

    def reconnect(self, timeout=10):
        """D9: tear down a dead telnet connection and establish a fresh
        one to the same host/port. A fresh TerminalScreen + TelnetHandler
        are used (a new TCP connection means the server expects fresh IAC
        negotiation and starts drawing from its own login entry point --
        reusing the old pyte screen would show stale frozen content under
        newly-arriving bytes). The logger and history are preserved so
        the transcript/recent-events stay continuous across the drop."""
        try:
            self.conn.close()
        except Exception:
            pass
        self.terminal = TerminalScreen()
        self.negotiator = TelnetHandler()
        self.conn = TelnetConnection(self.host, self.port, self.terminal, self.negotiator, logger=self.logger)
        self.lock = self.conn.lock
        # A fresh TCP connection gets its own fresh game-select allowance
        # -- see the flags' own __init__ comment above.
        self.game_select_answered = False
        self.game_select_letter_sent = False
        self.conn.connect(timeout=timeout)

    # -- rendering ---------------------------------------------------

    def render(self):
        with self.lock:
            return self.terminal.render_cropped()

    def render_with_color(self):
        """(rows, color_map) captured under ONE lock acquisition (D13) —
        calling render() and terminal.color_map() as two separate calls
        risks a byte arriving in between, shifting the bounding box and
        producing a color map that no longer lines up with the text."""
        with self.lock:
            return self.terminal.render_cropped(), self.terminal.color_map()

    def render_raw(self):
        with self.lock:
            return self.terminal.raw_display()

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())

    def cursor_pos(self):
        """Thread-safe read of the pyte cursor's {"x","y"} -- the caret
        position `tw attach`'s MANUAL-mode keypress echo draws at. Same
        locking discipline as render()/render_with_color(): the reader
        thread mutates the pyte screen (cursor included) under `self.lock`,
        so any other thread reading it must take the same lock."""
        with self.lock:
            return self.terminal.cursor()

    # -- credits supervision (WO-FA7a) --------------------------------

    def observe_credits(self, text):
        """Passive credits-supervision capture point: whenever `text` (any
        settled screen this session has rendered) carries a STRICT "you
        have N credits" balance (`state_parser.credits_balance()` -- NEVER
        the looser `parse_state()`'s own `credits` field, which a port's
        own price quote would satisfy just as well and misreport as a real
        balance), mirrors it onto `last_credits`/`last_credits_ts` (see
        those fields' own `__init__` comment). A screen with no balance
        line at all (`credits_balance(text)` is `None`) leaves both fields
        UNTOUCHED -- the whole non-clobber point: a caller can trust the
        last-known balance (and its own, now-stale ts) stays visible
        across intervening non-balance screens.

        REFACTORED (WO-FA7a revise 3, mack-confirmed CRITICAL): this used
        to live as a protocol.py-only helper (`_capture_credits`), called
        from just the two `tw do`/`read`/`screen`/`state` dispatch
        chokepoints -- but `replay_skill`/`play_skill` (skills.py, the
        AUTO-LOOP driver's actual per-step engine) render and classify
        every screen WITHOUT ever routing through protocol.py's
        `build_response()`, so the E2 supervised-run's entire execution
        path (AUTO_LOOP -> loop_player -> replay_skill) left `tw status`
        credits permanently stale/None -- exactly the run this surface
        exists to observe. Living here as a plain `Session` method (not a
        protocol.py free function) lets skills.py call it directly without
        importing protocol.py (which imports skills.py -- a straight
        `from .protocol import _capture_credits` would circular-import).
        Called from: `protocol.build_response()`, the `state` verb,
        `skills.replay_skill()`'s per-step loop, `skills.play_skill()`'s
        own per-cycle floor-check render, and `crawl_driver.py`'s
        per-screen crawl factory -- every autonomous settled-screen site
        this codebase has today.

        KNOWN NON-COVERED PATH (WO-FA7a revise 3, mack HIGH #2, documented
        not fixed): `tw attach`'s raw per-keystroke path (`daemon.py`'s
        `_handle_attach` -> `send_raw()`) never calls this -- it's a raw,
        UNsettled byte pass-through with no render/classify/build_response
        step to hook, and attach is a HUMAN driving, not the autonomous E2
        mode this surface exists for. Left uncovered deliberately rather
        than adding a per-keystroke capture that would read mid-transition
        screens; self-revealing anyway, since `credits_age_ms` (protocol.py
        `status` verb) just keeps growing while a human plays manually,
        which is the CORRECT signal for "no autonomous run is feeding
        this" -- not a silent gap.

        ATOMIC WRITE (WO-FA-SAFE, Rook must-fix #3): both fields are set
        under `self.lock` -- the same lock `render()`/`cursor_pos()` already
        use to guard concurrent `Session` state -- so a reader can never
        observe a torn (old-balance/new-ts) pair. Before this fix the two
        assignments were unlocked, plain statements; a concurrent `tw
        status` (read-only-always-allowed, calls `observe_credits()` on the
        command thread) landing between them could read the OLD balance
        alongside the NEW ts, understating the reported age -- for a
        passive `status` display that's cosmetic, but the credit-floor
        stop-loss decision sites (`loop_player.py`/`autopilot.py`) trust
        this same pair to decide HALT-vs-proceed, where a falsely-fresh
        stale balance is a real over-spend defeat. `credits_snapshot()`
        below reads both fields back under the SAME lock -- callers that
        need a non-torn pair (not just the write itself being atomic) must
        use it rather than two separate `getattr()`s."""
        credits = credits_balance(text)
        if credits is not None:
            with self.lock:
                self.last_credits = credits
                self.last_credits_ts = time.monotonic()

    def credits_snapshot(self):
        """Atomic `(last_credits, last_credits_ts)` read (WO-FA-SAFE, Rook
        must-fix #3) -- both fields read under the SAME lock
        `observe_credits()` writes them under, so a caller can never see a
        torn pair (an old balance paired with a new ts, understating
        staleness). This is the strict source the credit-floor stop-loss
        decision sites use (`loop_player.py`'s per-cycle floor-check,
        `autopilot.py`'s `dry_run_tick()`/`live_tick()` -> `assess()`) --
        NOT `parse_state()`'s own looser `credits` field, which a port's
        own price quote satisfies just as well (see `observe_credits()`'s
        own docstring for why the source split exists at all).

        Inherits `credits_balance()`'s documented FORGED-BALANCE residual
        (state_parser.py, FA9-class roadmap prerequisite): a forged
        in-band "You have N credits" broadcast landing after the real
        balance line on some earlier screen would have already poisoned
        `last_credits` at capture time, before this method ever runs --
        SOLO-safe today (no other player exists on a crawl_sacrificial game
        to author such a forgery); arming any consumer of this snapshot in
        multiplayer REQUIRES WO-FA9 first."""
        with self.lock:
            return self.last_credits, self.last_credits_ts

    # -- settle-detection protocol (see settle.wait_for_settle) ------

    @property
    def rx_count(self):
        return self.conn.rx_count

    @property
    def last_rx(self):
        return self.conn.last_rx

    def clock(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        return wait_for_settle(self, wait_prompt=wait_prompt, timeout_s=timeout, debounce_ms=debounce_ms)

    # -- sending -------------------------------------------------------

    def send(self, text, enter=True, secret=False):
        with self.send_lock:
            now = time.monotonic()
            delta = now - self._last_send_time
            if delta < MIN_SEND_GAP_S:
                time.sleep(MIN_SEND_GAP_S - delta)
            self.conn.send_text(text, enter=enter, secret=secret)
            self._last_send_time = time.monotonic()
            self.last_sent = "<redacted>" if secret else text
            self.last_sent_ts = self._last_send_time

    def send_raw(self, data: bytes, control_lock=None):
        """Exact-byte pass-through for interactive `tw attach` keystrokes
        -- no text encoding, no auto-appended \\r\\n (unlike send()); the
        caller (daemon.py's CommandHandler._handle_attach) has already
        decided the exact wire bytes for this keystroke. Still goes
        through the same send_lock + MIN_SEND_GAP_S anti-hammer
        guardrail as send() -- a human mashing keys deserves the same
        courtesy to the server as a scripted `do`.

        `control_lock`, when provided (the ONLY real caller passes the
        daemon's own ControlLock -- see CommandHandler._handle_attach),
        gates a bounded wait for a FENCED in-flight ai_pilot dispatch
        (WO-CLEANPREEMPT, control_lock.ControlLock.take_human()) to
        actually clear before THIS byte reaches the wire: take_human()
        itself never blocks or refuses while a dispatch is mid-flight
        (the human always wins immediately) -- the wait happens HERE
        instead, one layer later, at the point a real byte is about to
        go out, so the fenced dispatch's own in-flight send-then-settle
        window always closes before any human byte can interleave with
        it on the wire. Bounded by `_FENCE_WAIT_TIMEOUT_S` -- a courtesy
        ordering wait, never a second refusal path; the keystroke is
        always eventually sent even if the bound is reached. `None` (the
        default) is a complete no-op, matching every other optional-
        collaborator convention in this codebase (protocol.py's
        `getattr(..., None)` guards).

        WO-CLEANPREEMPT (secret sub-diff, cipher's proven leak): a raw
        keystroke has no `secret` flag of its own the way `send()`'s
        caller can supply one -- so THIS function decides it, fresh,
        every call: right after the fence-wait resolves (never before --
        mack's staleness finding: the screen can transition to a secret
        prompt DURING an up-to-`_FENCE_WAIT_TIMEOUT_S` wait, and a
        pre-wait decision would under-redact against that later, real
        prompt) and immediately before the byte reaches the wire, this
        re-renders the CURRENT screen and classifies its prompt line via
        `classify.is_probable_secret_prompt()` (a deliberately broad,
        FAIL-SAFE heuristic -- see that function's own docstring for
        what it catches and its documented residual). The result gates
        `TelnetConnection.send_bytes(secret=...)` (redacts the transcript
        LOG the same way `send_text(secret=True)` already does) and is
        exposed via `self.last_sent_secret` so `CommandHandler.
        _handle_attach` can thread the SAME decision into `protocol.
        record_attach_keystroke()`'s ledger row -- one decision, read by
        all three sinks (log, ledger, and `last_sent` below), never
        independent (and therefore possibly disagreeing) derivations.
        `last_sent` -- the THIRD sink (`tw status`'s `sent_input` field
        reads it straight off this attribute, and the spectate
        TX-channel display reads `sent_input` too) -- is now redacted
        the SAME "<redacted>" way `send()` already redacts it for a
        `secret=True` do/send call."""
        if control_lock is not None:
            deadline = time.monotonic() + _FENCE_WAIT_TIMEOUT_S
            while control_lock.is_driver_fenced() and time.monotonic() < deadline:
                time.sleep(_FENCE_WAIT_POLL_S)
        rows = self.render()
        prompt_line = rows[-1].strip() if rows else ""
        secret = is_probable_secret_prompt(prompt_line)
        with self.send_lock:
            now = time.monotonic()
            delta = now - self._last_send_time
            if delta < MIN_SEND_GAP_S:
                time.sleep(MIN_SEND_GAP_S - delta)
            self.conn.send_bytes(data, secret=secret)
            self._last_send_time = time.monotonic()
            self.last_sent = "<redacted>" if secret else data.decode("latin-1", errors="replace")
            self.last_sent_ts = self._last_send_time
            self.last_sent_secret = secret

    # -- history ---------------------------------------------------------

    def record_history(self, verb, args, prompt, classification, settled_reason):
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "verb": verb,
            "args": args,
            "prompt": prompt,
            "classification": classification,
            "settled_reason": settled_reason,
        }
        self.history.append(entry)
        if len(self.history) > self._history_cap:
            self.history.pop(0)

    def close(self):
        self.conn.close()
        self.logger.close()
