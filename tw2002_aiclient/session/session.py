"""Session — the live telnet+pyte state a daemon process owns.

Implements the settle-detection protocol (`.rx_count`, `.last_rx`,
`.clock()`, `.sleep()`, `.render_text()`) directly, so `settle.wait_for_settle`
can be handed `self`.

Ported from `archive/pre-rebirth-2026-07-23/code/twclient/session.py`
(WO-P2-020, Wave-2) -- a BOUNDED port of the connect -> send -> render ->
settle -> classify core only. See this module's own comments (marked
"WO-P2-020 CUT") for what the archive coupled in that is deliberately NOT
ported here (control_lock, the trace ledger, state_parser's credits/turns/
fighters supervision) -- those land in later work orders once their own
modules exist under `tw2002_aiclient/session/`.
"""

import threading
import time

from .classify import classify_screen, is_probable_secret_prompt
from .connection import TelnetConnection
from .iac import TelnetHandler
from .logging_util import TranscriptLogger
from .settle import wait_for_settle
from .terminal import TerminalScreen

MIN_SEND_GAP_S = 0.15  # guardrail: no hammering the server

# WO-CLEANPREEMPT (archive): bounded wait for a FENCED in-flight app-driven
# dispatch to actually release before a human `tw attach` keystroke reaches
# the wire (see Session.send_raw()'s own docstring). Generous relative to
# `do`'s own default settle timeout (protocol.py's "timeout" arg, 8.0s) so
# an ordinary in-flight dispatch clears well within it; a genuinely wedged
# dispatch (one that never releases its control-lock hold at all -- which
# would already violate every OTHER try/finally-paired guarantee in this
# codebase) is the only way this bound is ever actually reached, and even
# then this is a courtesy ORDERING wait, never a second refusal path -- the
# keystroke is sent regardless once the bound expires.
_FENCE_WAIT_TIMEOUT_S = 10.0
_FENCE_WAIT_POLL_S = 0.02

# canon: architecture/session-engine.md "Send-time actor tag `{app, human}`
# + `session_id`" -- the only two live senders in the reborn model (the AI
# is a retrospective author, never a live sender). Applied HERE, at the
# carrier, per that section's own wording: "the tag is applied here, at the
# carrier; the full ledger-row schema ... is owned by the Trace Ledger."
# The archive's session.py never actually carried a sender argument at all
# (the {ai,trainer,human} vocabulary the Code Divergence section flags
# lived one layer up, in protocol.py's dispatch and loop_player.py) --
# this port adds the tag at the choke point canon specifies, scoped to
# just the two reborn-legal values.
VALID_SENDERS = ("app", "human")


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

        # The daemon's own continuous per-run id (canon: session-engine.md
        # "the daemon's own continuous session_id ... reused as-is so a
        # ledger row and its transcript file correlate for free") -- the
        # TranscriptLogger already mints one; Session just exposes it under
        # the same name canon's ledger schema will key on. Fixed for the
        # life of this Session, including across reconnect() (a dropped
        # TCP connection is not a new daemon run).
        self.session_id = self.logger.session_id

        # TX channel: the most recent thing sent to the game, threaded
        # through the daemon's own response-building choke point so every
        # watch event -- App-dispatched or human `attach` alike -- can show
        # it, from ONE chokepoint (send()/send_raw() below), the same way
        # a build_response()-style assembly point is the single chokepoint
        # on the receive side. `None` until the first send; a `secret=True`
        # send() -- and a secret-prompt send_raw() attach keystroke too --
        # stores the SAME "<redacted>" placeholder the log/ledger sinks
        # use, never the real password text.
        self.last_sent = None
        self.last_sent_ts = None
        # The {app,human} tag actually applied to `last_sent`, alongside it
        # -- so a later ledger-row writer can read (text, sender, ts) back
        # as one atomic-enough triple without re-deriving the sender.
        self.last_sender = None
        # send_raw()'s OWN send-time secret decision (is_probable_secret_
        # prompt() against the CURRENT screen, evaluated right before the
        # byte reaches the wire -- see send_raw()'s docstring), exposed
        # here so a daemon-side attach handler can read the SAME decision
        # back after the call and thread it into a ledger row, rather than
        # re-deriving it a second, potentially-stale way. `send()`'s own
        # `secret` argument is caller-supplied and unrelated to this --
        # this attribute is ONLY ever set by send_raw(), defaulting False
        # until the first attach keystroke.
        self.last_sent_secret = False

        self.history = []  # ring buffer of recent do/read events
        self._history_cap = 200

        # D9 reconnect + login-replay: set once login succeeds against a
        # profile, so a later drop can be auto-recovered without the
        # caller re-specifying which credential to replay.
        self.auto_login_profile = None

        # Safety fix (archive): once the login automaton has genuinely
        # CLEARED the real game-select screen on this TCP connection (sent
        # the configured letter AND a later classification is no longer
        # `game_select`), it refuses to send `profile.game_letter` again --
        # closing the `ensure`-mid-session stale-pyte-buffer misfire vector
        # at the SOURCE (a stale game-select header/marker left over from
        # earlier in the connection, plus a later ordinary screen sharing
        # the same generic prompt, could otherwise get misclassified as
        # game_select and re-answered with a blind keystroke) -- independent
        # of any classify.py heuristic. NOT latched on send-confirm alone: a
        # false-positive idle settle that leaves the CURRENT screen still
        # classified as `game_select` must remain retryable. PER-CONNECTION,
        # not per-login-run: reset below in reconnect() so a genuinely fresh
        # connection (a D9 reconnect-replay, or a fresh cold-start login)
        # can still answer game-select normally.
        self.game_select_answered = False
        # Set True the first time the login automaton sends
        # `profile.game_letter` on this connection; used with
        # `game_select_answered` above to know a non-`game_select`
        # classification means we cleared, not skipped.
        self.game_select_letter_sent = False

    def start(self, timeout=10):
        self.conn.connect(timeout=timeout)

    def mark_profile(self, profile_name):
        """Record which profile last successfully logged this session in
        -- a later auto-reconnect replays login against this profile."""
        self.auto_login_profile = profile_name

    def reconnect(self, timeout=10):
        """D9: tear down a dead telnet connection and establish a fresh
        one to the same host/port. A fresh TerminalScreen + TelnetHandler
        are used (a new TCP connection means the server expects fresh IAC
        negotiation and starts drawing from its own login entry point --
        reusing the old pyte screen would show stale frozen content under
        newly-arriving bytes). The logger, `session_id`, and history are
        preserved so the transcript/recent-events stay continuous across
        the drop."""
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
        """(rows, color_map) captured under ONE lock acquisition -- calling
        render() and terminal.color_map() as two separate calls risks a
        byte arriving in between, shifting the bounding box and producing
        a color map that no longer lines up with the text."""
        with self.lock:
            return self.terminal.render_cropped(), self.terminal.color_map()

    def render_raw(self):
        with self.lock:
            return self.terminal.raw_display()

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self.render())

    def cursor_pos(self):
        """Thread-safe read of the pyte cursor's {"x","y"} -- the caret
        position an attach surface's MANUAL-mode keypress echo draws at.
        Same locking discipline as render()/render_with_color(): the
        reader thread mutates the pyte screen (cursor included) under
        `self.lock`, so any other thread reading it must take the same
        lock."""
        with self.lock:
            return self.terminal.cursor()

    def current_prompt_line(self):
        """The last non-empty-cropped row of the CURRENT render -- the
        single line gate anchors (classify.classify_screen, is_probable_
        secret_prompt) are evaluated against. Shared by classify() and
        send_raw() below so both agree on what "the current prompt" means."""
        rows = self.render()
        return rows[-1].strip() if rows else ""

    def classify(self):
        """Classify the CURRENT rendered screen via `classify.
        classify_screen()` -- the canonical live path (gate anchors
        checked against the current prompt line only, content anchors
        against the whole screen; see that function's own docstring for
        the anchor-precedence rationale). This is the classify hook the
        daemon's response-building choke point (Wave-3) drives off of."""
        rows = self.render()
        return classify_screen(self.render_text(rows), rows[-1].strip() if rows else "")

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

    def send(self, text, enter=True, secret=False, sender="app"):
        """Automated/scripted send -- text plus an optional auto-appended
        CRLF. `sender` is the canon `{app, human}` send-time actor tag
        (session-engine.md); defaults to `"app"` since every caller of
        this method today is App-side dispatch (do/haggle/auto-loop), not
        a raw human keystroke (that path is send_raw() below, which
        defaults to `"human"`)."""
        if sender not in VALID_SENDERS:
            raise ValueError(f"sender must be one of {VALID_SENDERS}, got {sender!r}")
        with self.send_lock:
            now = time.monotonic()
            delta = now - self._last_send_time
            if delta < MIN_SEND_GAP_S:
                time.sleep(MIN_SEND_GAP_S - delta)
            self.conn.send_text(text, enter=enter, secret=secret)
            self._last_send_time = time.monotonic()
            self.last_sent = "<redacted>" if secret else text
            self.last_sent_ts = self._last_send_time
            self.last_sender = sender
            self.last_sent_secret = secret

    def send_raw(self, data: bytes, control_lock=None, sender="human"):
        """Exact-byte pass-through for interactive `tw attach` keystrokes
        -- no text encoding, no auto-appended \\r\\n (unlike send()); the
        caller has already decided the exact wire bytes for this
        keystroke. Still goes through the same send_lock + MIN_SEND_GAP_S
        anti-hammer guardrail as send() -- a human mashing keys deserves
        the same courtesy to the server as a scripted `do`. `sender`
        defaults to `"human"` since this is the interactive-keystroke
        path; still validated against the same canon `{app, human}` tag
        set as send() rather than assumed.

        `control_lock`, when provided, gates a bounded wait for a FENCED
        in-flight App-driven dispatch to actually clear before THIS byte
        reaches the wire: the lock itself never blocks or refuses the
        human (the human always wins immediately) -- the wait happens
        HERE instead, one layer later, at the point a real byte is about
        to go out, so the fenced dispatch's own in-flight send-then-settle
        window always closes before any human byte can interleave with it
        on the wire. Bounded by `_FENCE_WAIT_TIMEOUT_S` -- a courtesy
        ordering wait, never a second refusal path; the keystroke is
        always eventually sent even if the bound is reached. `None` (the
        default) is a complete no-op -- WO-P2-020 CUT: the control-lock
        module this collaborator comes from (`control_lock.py`) has not
        been ported yet, so this parameter stays optional/duck-typed
        exactly as it was in the archive; nothing here assumes it exists.

        A raw keystroke has no `secret` flag of its own the way `send()`'s
        caller can supply one -- so THIS function decides it, fresh, every
        call: right after the fence-wait resolves (never before -- the
        screen can transition to a secret prompt DURING an up-to-
        `_FENCE_WAIT_TIMEOUT_S` wait, and a pre-wait decision would
        under-redact against that later, real prompt) and immediately
        before the byte reaches the wire, this re-renders the CURRENT
        screen and classifies its prompt line via `classify.
        is_probable_secret_prompt()` (a deliberately broad, FAIL-SAFE
        heuristic -- see that function's own docstring for what it catches
        and its documented residual). The result gates
        `TelnetConnection.send_bytes(secret=...)` (redacts the transcript
        LOG the same way `send_text(secret=True)` already does) and is
        exposed via `self.last_sent_secret` so a daemon-side attach
        handler can thread the SAME decision into its own ledger row,
        rather than re-deriving it a second, potentially-stale way.
        `last_sent` is redacted the SAME "<redacted>" way `send()` already
        redacts it for a `secret=True` do/send call."""
        if sender not in VALID_SENDERS:
            raise ValueError(f"sender must be one of {VALID_SENDERS}, got {sender!r}")
        if control_lock is not None:
            deadline = time.monotonic() + _FENCE_WAIT_TIMEOUT_S
            while control_lock.is_driver_fenced() and time.monotonic() < deadline:
                time.sleep(_FENCE_WAIT_POLL_S)
        prompt_line = self.current_prompt_line()
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
            self.last_sender = sender

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
