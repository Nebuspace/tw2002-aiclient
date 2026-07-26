"""Session — the live telnet+pyte state a daemon process owns.

Implements the settle-detection protocol (`.rx_count`, `.last_rx`,
`.clock()`, `.sleep()`, `.render_text()`) directly, so `settle.wait_for_settle`
can be handed `self`.

Ported from `archive/pre-rebirth-2026-07-23/code/twclient/session.py`
(WO-P2-020, Wave-2) -- a BOUNDED port of the connect -> send -> render ->
settle -> classify core only. See this module's own comments (marked
"WO-P2-020 CUT") for what the archive coupled in that is deliberately NOT
ported here (the trace ledger, state_parser's turns/fighters supervision)
-- those land in later work orders. **Credits supervision landed in
WO-P2-G4-X5** (`observe_credits`/`credits_snapshot` below): it is the
substrate the stop-loss floor reads, and a floor without it would be a
flag the runtime cannot enforce. `control_lock` is owned
by the daemon and passed into `send_raw` when attach drives; this module
only duck-types `is_driver_fenced()` at the send choke.
"""

import threading
import time

from .classify import classify_screen, is_probable_secret_prompt
from .connection import TelnetConnection, tx_failure_phrase
from .iac import TelnetHandler
from .logging_util import TranscriptLogger
from .settle import MATCH_SCOPE_SCREEN, wait_for_settle
from .state_parser import (
    OUTCOME_READ,
    CreditsSnapshot,
    credits_never_observed,
    read_credits_balance,
)
from .terminal import TerminalScreen
from .transcript_tail import TranscriptTail

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
# After the courtesy bound, if the fence is STILL raised, the predecessor is
# almost certainly wedged inside blocking ``sendall`` (WO-WEDGED-SEND-FENCE-
# STICKS). Unblocking the socket lets its ``finally`` clear the fence; this
# short second poll is only to absorb that release, not a second 10s tax.
_FENCE_UNBLOCK_WAIT_S = 1.0

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

        # WO-P3-041: bounded redacted transcript ring for the cockpit's
        # [LOGS] band (canon: trainer-cockpit.md), served on the `status`
        # verb (protocol.py) as `log_tail`. Redaction happens AT INSERT,
        # at the same send()/send_raw() choke points that already decide
        # `secret` for the real transcript logger -- see transcript_tail.py's
        # own docstring for why a payload can never reach it. Survives
        # reconnect() (not reset there, unlike self.terminal/self.negotiator
        # -- a dropped TCP connection is not a new operator-visible session,
        # same reasoning as self.logger/self.history below).
        self.tail = TranscriptTail()

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
        # RX-side counterpart to last_sent/last_sent_ts (WO-P2-G4-X5): the
        # most recent STRICT credits balance any settled screen stated, plus
        # the monotonic instant it was seen. Written ONLY by
        # observe_credits() and read ONLY through credits_snapshot(), both
        # under self.lock -- never touched directly by anything else, which
        # is what makes the pair non-tearable. `None`/`None` until the first
        # balance-bearing screen, and DELIBERATELY never cleared by a later
        # screen that states no balance: a reading that vanished would look
        # to the floor exactly like one that was never taken, and the two
        # want different repairs. Credits are not secret -- this pair goes
        # nowhere near the redaction sinks above.
        self.last_credits = None
        self.last_credits_ts = None
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
        # `secret` argument is caller-supplied, and BOTH senders record it
        # here: `send()` and `send_raw()` each assign this attribute from
        # their own `secret` argument. Defaults False until the first send
        # of either kind.
        #
        # This comment previously claimed `send_raw()` was the ONLY writer.
        # That was false -- AST-verified, the attribute is stored in
        # `__init__`, `send()` and `send_raw()` -- and it cost a lane a
        # wrong test assertion, because the reader trusted the comment over
        # the code. Corrected rather than deleted so the trap is legible:
        # an attribute described as single-writer is exactly the kind of
        # claim a caller will build an inference on.
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
            # Deliberately broad AND silent -- both on purpose, not an
            # oversight:
            #  - BROAD: `self.conn` is already dead (that's WHY reconnect()
            #    was called); tearing it down can raise near anything
            #    depending on how the far end and the OS socket layer
            #    react to closing an already-broken connection. Reconnect's
            #    job is to land a working NEW connection, never to salvage
            #    the old one, so no failure here may block the fresh
            #    TelnetConnection built just below.
            #  - SILENT: Cipher/redaction doctrine (canon: doctrine/
            #    secrets-and-credentials.md) -- this session carries
            #    TradeWars server payloads and operator-typed input, and
            #    str(e) on an arbitrary exception could echo that content.
            #    Same reasoning watch.py's WatchHub documents at its own
            #    `except Exception as e` sites (type(e).__name__ only,
            #    never str(e)). The parallel here is NOT that there's no
            #    mechanism available -- `self.logger` (TranscriptLogger,
            #    still open, passed into the fresh TelnetConnection just
            #    below) is sitting right there and could easily be handed
            #    a type name. It is deliberately NOT used for this
            #    exception: the doctrine governs regardless of what
            #    mechanism happens to be in scope, so nothing is recorded
            #    at all, not even type(e).__name__. WatchHub has a field
            #    and records type-name-only; reconnect has a logger and
            #    records nothing -- same doctrine, two different surfaces.
            # Narrowing this except to specific socket/OSError types is a
            # SEPARATE hardening ticket -- deliberately NOT done here.
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

    # -- credits supervision (WO-P2-G4-X5) ---------------------------
    #
    # The stop-loss rail's whole substrate. Canon
    # (`doctrine/action-safety-guards.md` §"Structural rails") requires the
    # floor to be "read from the *strict* last-known confirmed balance and
    # fail-closed: an unknown or stale balance HALTs". These two methods are
    # "last-known" and "how stale"; the fail-closed decision itself lives in
    # `loops/player.py`, which owns every refusal.

    def observe_credits(self, text):
        """Capture a STRICT balance off a settled screen, if this one states
        one. Called from every settled-render site the App drives.

        **Non-clobber.** A screen that states no balance leaves the sticky
        pair untouched, so an intervening command prompt does not erase what
        the last port screen said -- it just lets the reading age, which is
        what `credits_snapshot()` reports and what the floor's staleness gate
        acts on. A screen whose balance claim is DAMAGED
        (`state_parser.OUTCOME_UNREADABLE`, a render taken mid-paint) is
        likewise not written: "I could not finish reading it" is not a
        balance, and collapsing it into one is the defect this repo has now
        fixed six times.

        **Strict, never `parse_state()`'s looser field.** The extraction is
        `state_parser.read_credits_balance`, which refuses the bare
        "N credits" mention a port's own price quote satisfies. AP-13 states
        why in one sentence: using the loose field for a cash floor "means
        the stop-loss can be defeated by a price quote on the wrong screen --
        exactly what happened live before this was fixed."

        **Both fields under ONE lock hold.** `self.lock` is the same lock
        `render()` takes, so a concurrent reader can never see a torn pair.
        The archive shipped these as two unlocked statements and had to fix
        it: a reader landing between them pairs an OLD balance with a NEW
        timestamp, understating the age, "where a falsely-fresh stale balance
        is a real over-spend defeat."
        """
        read = read_credits_balance(text)
        if read.outcome != OUTCOME_READ:
            return
        with self.lock:
            self.last_credits = read.balance
            self.last_credits_ts = time.monotonic()

    def credits_snapshot(self):
        """What this session knows about the balance right now, as a
        validated `state_parser.CreditsSnapshot`.

        Returns an AGE, not a timestamp, and computes it here -- inside the
        same lock hold that reads the pair. The consumer is a pure decision
        function with no clock of its own, and handing it a raw `monotonic()`
        stamp would put the subtraction on the far side of a module boundary
        where a second clock could creep in. One clock, one hold, one value.

        `absent` when nothing has ever been observed. That is the honest
        answer and the floor turns it into a HALT (`credits_unknown`) -- it
        is never softened into "assume we're fine", which is the whole point
        of a stop-loss.
        """
        with self.lock:
            balance = self.last_credits
            ts = self.last_credits_ts
            if balance is None or ts is None:
                return credits_never_observed()
            # max(0.0, ...) rather than trusting the subtraction: the
            # CreditsSnapshot type rejects a negative age (it would read as
            # fresher-than-now, the fail-OPEN direction), and a clamp here
            # keeps a monotonic hiccup from raising out of a status read.
            # It can only ever make the age look OLDER, never younger.
            return CreditsSnapshot(
                outcome=OUTCOME_READ,
                balance=balance,
                age_s=max(0.0, time.monotonic() - ts),
            )

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

    def wait_settle(
        self,
        wait_prompt=None,
        timeout=8.0,
        debounce_ms=350,
        prompt_requires_new_bytes=False,
        match_scope=MATCH_SCOPE_SCREEN,
    ):
        """`prompt_requires_new_bytes` and `match_scope` are pure
        pass-throughs to `settle.wait_for_settle` -- this method holds no
        policy of its own and must not acquire any, since `do` (which sets
        both) and `read` (which must set neither) reach settle detection
        through this one door. See that module's "Stale pre-send prompt
        match" and "Stale-line match" docstring sections. Any test double
        standing in for a Session on the `do` path has to accept these
        arguments too.

        `match_scope`'s default is `MATCH_SCOPE_SCREEN` -- the same value
        `wait_for_settle` already defaults to, restated here only so the
        door stays neutral rather than opinionated. It is deliberately NOT
        `MATCH_SCOPE_PROMPT_LINE`: canon's P-SETTLE-LINE
        (`canon/research/tw2002-screen-patterns.md`) leaves "which canon
        doc governs default `match_scope`" an open question and rules
        "until ruled, do not flip defaults in a drive-by tip; pin
        prompt-line scope where a WO explicitly Accepts it." A default
        here would be exactly the drive-by flip that forbids -- and would
        silently take `read` with it, since `read` shares this door.
        WO-DO-PROMPT-LINE-PIN therefore pins the scope at the `do` CALL
        SITE in `protocol.py`, where the pin is visible and scoped to the
        one verb that Accepts it.
        """
        return wait_for_settle(
            self,
            wait_prompt=wait_prompt,
            timeout_s=timeout,
            debounce_ms=debounce_ms,
            prompt_requires_new_bytes=prompt_requires_new_bytes,
            match_scope=match_scope,
        )

    # -- sending -------------------------------------------------------

    def _tail_send(self, secret, display_line):
        """Append one send to the LOGS-band ring, honoring the `secret`
        decision the caller already made.

        The single copy of this branch for both send choke points and both
        their outcomes -- `secret` is consumed here, never derived (see
        `transcript_tail.py`'s own docstring: `append_redacted()` cannot be
        handed a payload even by mistake).
        """
        if secret:
            self.tail.append_redacted()
        else:
            self.tail.append_line(display_line)

    def _tail_send_failed(self, secret, display_line, exc):
        """Record a send that did NOT complete, on the operator-visible
        LOGS-band surface (WO-AUDIT-TX-RECORD-HONESTY, session-audit F6).

        Before this, a failed send left the transcript LOG asserting a send
        that never completed while this ring -- and `last_sent` -- recorded
        nothing at all, so the two records of the same event permanently
        disagreed. `connection.py` now writes an honest failure record; this
        is the matching half. Silence here would be the SAME defect wearing
        the opposite costume: bytes may genuinely have reached the server
        (see connection.py's docstring, fact 1), and a LOGS band showing
        nothing would erase that from the surface the operator actually
        watches.

        Two entries, deliberately: the ordinary send line first -- so the
        evidence of what was attempted survives, redacted exactly as a
        successful send of the same content would be -- then a payload-free
        failure line. The failure line is built from `connection.
        tx_failure_phrase()`, the same one home the transcript log's own tag
        uses, so these two surfaces cannot drift apart again; it carries an
        exception TYPE name and fixed text only, never `str(exc)` and never
        any part of the send, so it is safe verbatim on the secret path too.

        **Deliberate asymmetry with the transcript LOG, documented here so
        it doesn't read as an oversight.** `connection.py` folds the failure
        into the SINGLE record's own channel tag rather than writing a
        second, retracting record; this ring does the opposite. The reason
        is the redaction guarantee, not convenience: keeping the send line
        as a plain `_tail_send()` call means EVERY secret-bearing entry that
        ever reaches this ring still goes through `append_redacted()`, on
        the failure path exactly as on the success path. Folding the failure
        text into one line instead would mean either re-typing
        `append_redacted()`'s marker wording here (the very drift
        `transcript_tail.py` documents itself against) or routing a secret
        send through `append_line()` -- which `tests/test_transcript_tail.py`
        pins as explicitly NOT a guard. The log file has no equivalent
        constraint (its `direction` tag is already a free-form parameter of
        both sinks), and it is the surface where a long-lived, greppable,
        tail-able file could genuinely separate a claim from its retraction;
        this ring is written atomically under `send_lock` and rendered as
        adjacent lines, newest-visible, in the cockpit's LOGS band.
        """
        self._tail_send(secret, display_line)
        self.tail.append_line(f"<<send failed: {tx_failure_phrase(exc)}>>")

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
            # A send that raises leaves `last_sent`/`last_sent_ts`/
            # `last_sender`/`last_sent_secret` and `_last_send_time`
            # DELIBERATELY untouched, exactly as before this work order:
            # they keep describing the last send that actually completed,
            # which stays a true statement. Only the transcript surfaces
            # (`conn`'s log, and the ring below) record the attempt --
            # `last_sent` is a "what is the current state" field, not a
            # record of history, and the same guardian.py already applies
            # to its own keepalive stamp ("do not stamp" on OSError).
            try:
                self.conn.send_text(text, enter=enter, secret=secret)
            except BaseException as exc:
                self._tail_send_failed(secret, f"{sender}> {text}", exc)
                raise
            self._last_send_time = time.monotonic()
            self.last_sent = "<redacted>" if secret else text
            self.last_sent_ts = self._last_send_time
            self.last_sender = sender
            self.last_sent_secret = secret
            # Same `secret` decision that just gated conn.send_text()'s own
            # log_redacted()/log_raw() choice, above -- never re-derived.
            self._tail_send(secret, f"{sender}> {text}")

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
        default) is a complete no-op. Duck-typed: only
        `is_driver_fenced()` is required (real collaborator =
        `tw2002_aiclient.session.control_lock.ControlLock`, owned by the
        daemon and passed from attach).

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
            # Bound expired and still fenced: do NOT clear the fence here
            # (that would be a second driver / TOCTOU against a live wire
            # writer). Unblock the socket so the wedged run's own finally
            # can ``leave_auto_loop``; generation tokens already prevent a
            # later run from laundering this fence away (see control_lock).
            if control_lock.is_driver_fenced():
                self.conn.force_unblock_sends()
                unblock_deadline = time.monotonic() + _FENCE_UNBLOCK_WAIT_S
                while control_lock.is_driver_fenced() and time.monotonic() < unblock_deadline:
                    time.sleep(_FENCE_WAIT_POLL_S)
        prompt_line = self.current_prompt_line()
        secret = is_probable_secret_prompt(prompt_line)
        with self.send_lock:
            now = time.monotonic()
            delta = now - self._last_send_time
            if delta < MIN_SEND_GAP_S:
                time.sleep(MIN_SEND_GAP_S - delta)
            # Display form computed up front so the failure path can record
            # WHAT was attempted without assigning it to `last_sent` -- see
            # send()'s own comment for why a failed send leaves `last_sent`
            # and friends describing the last COMPLETED send instead.
            display = "<redacted>" if secret else data.decode("latin-1", errors="replace")
            try:
                self.conn.send_bytes(data, secret=secret)
            except BaseException as exc:
                self._tail_send_failed(secret, f"{sender}> {display}", exc)
                raise
            self._last_send_time = time.monotonic()
            self.last_sent = display
            self.last_sent_ts = self._last_send_time
            self.last_sent_secret = secret
            self.last_sender = sender
            # Same `secret` decision that just gated conn.send_bytes()'s own
            # log_redacted()/log_raw() choice, above -- never re-derived.
            self._tail_send(secret, f"{sender}> {display}")

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
