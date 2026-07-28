"""Raw socket telnet connection with a background reader thread.

One TelnetConnection = one telnet socket. The reader thread recv()s bytes,
runs them through the IAC handler (stripping negotiation, queuing replies),
feeds the clean data into pyte under `self.lock`, and stamps `last_rx` /
`rx_count` for the settle-detection layer. Anything touching the pyte
screen from another thread (the command-socket handler rendering a
response) must take the same lock.

**TX record honesty (WO-AUDIT-TX-RECORD-HONESTY, session-audit F6).** Every
TX record is written AFTER the `sendall()` it describes resolves, never
before, and a send that did not complete gets its own distinct record
instead of the ordinary one. This is a data-integrity property, not log
cosmetics: a retrospective AI teacher reads this transcript as evidence of
what the operator actually did, and a record of a send that never happened
is corrupted evidence -- corrupted precisely at the moments things were
going wrong, which are the moments most worth learning from.

Three facts about `socket.sendall()`, each established by execution on this
platform (CPython 3.14 / darwin) rather than read off the docs, force the
shape below:

  1. `sendall()` genuinely raises AFTER a partial transmission. Measured: a
     peer verifiably received 262144 bytes of the offered payload (content-
     checked as a true prefix) and `sendall()` still raised BrokenPipeError.
     So simply moving the old log call BELOW the wire would ERASE bytes that
     really did reach the server -- trading an over-record for an
     under-record, arguably worse, since the transcript would then disagree
     with what the game actually received.
  2. That partial failure is INDISTINGUISHABLE, from inside the except
     block, from a failure that sent nothing at all: a send on a
     already-dead socket raises BrokenPipeError with byte-identical args
     `(32, 'Broken pipe')`. No count is recoverable -- `characters_written`
     is a declared-but-unset `OSError` slot here, so reaching for it raises
     AttributeError. A record therefore can NEVER honestly state how much
     of a failed send got through.
  3. A SUCCESSFUL `sendall()` proves only that the local kernel accepted the
     bytes -- measured returning None while the peer had recv()'d nothing.
     So even the ordinary `TX` record has only ever meant "handed to the
     OS", never "the game received this". That pre-existing limit is named
     here rather than papered over; the success tag is deliberately left
     unchanged rather than churned for it.

Hence: one record per send, written once the outcome is known. On success,
byte-identical to what this module always wrote. On failure, the same
content routed through the same sink under a `-FAILED` channel tag naming
the exception TYPE (never its message -- see `tx_failure_phrase`) and
stating outright that delivery is unconfirmed.

**The `secret` flag is untouched by all of this.** Which sink fires for a
given `secret` value, where that decision is made (`Session.send()` /
`Session.send_raw()`, one layer up -- never re-derived here), and the fact
that `log_redacted()` takes no content parameter are all exactly as before.
A failed SECRET send routes to `log_redacted()` exactly like a successful
one: the failure record carries the marker only -- never the payload "for
diagnostics", and never a byte count, since a length is itself a leak
(canon: `canon/doctrine/secrets-and-credentials.md`, invariant 2).
"""

import socket
import threading
import time

# TX transcript channel tags. The `-FAILED` variants are built from these by
# `_tx_direction()` below.
TX_CHANNEL = "TX"
TX_IAC_CHANNEL = "TX-IAC"
_FAILED_SUFFIX = "-FAILED"

# Why every failure record says "delivery unconfirmed" rather than naming an
# amount: fact 2 in this module's docstring -- how much of a failed send
# reached the wire is not knowable from the exception, so a record that
# implied EITHER "none of it went" or "all of it went" would be inventing a
# fact. See `tx_failure_phrase()`.
_UNCONFIRMED_DELIVERY = "attempted, delivery unconfirmed"


class SendTextNotAString(TypeError):
    """``send_text`` was handed something that is not a ``str``.

    A ``TypeError`` subclass so anything already catching ``TypeError``
    keeps catching it, but with a name of its own because the daemon's
    wire rendering is ``internal_error:{type(e).__name__}`` and nothing
    else -- the class name is therefore the entire diagnostic budget, and
    ``AttributeError`` spends it saying "something was None somewhere".

    Never carries the offending VALUE. This is the send path that also
    carries passwords (`secret=True`), and a repr of the argument is
    precisely what `canon/doctrine/secrets-and-credentials.md` forbids
    reaching a log or a transcript.
    """


def tx_failure_phrase(exc) -> str:
    """The one wording for "this send did not complete", shared by every
    surface that has to say it.

    `connection.py`'s transcript channel tag and `session.py`'s LOGS-band
    marker both build from THIS function rather than each spelling the
    phrase themselves, so the two records of the same failure cannot drift
    apart -- which is the very class of defect this work order exists to
    close.

    Carries `type(exc).__name__` and NEVER `str(exc)`. The type name is
    structurally incapable of holding operator input or server payload,
    while an exception's message is not -- the same reasoning
    `Session.reconnect()` and `watch.WatchHub` already document at their own
    broad-except sites. The distinction earns its keep: "BrokenPipeError"
    (the server went away) and "TimeoutError" (the server stalled) are
    completely different lessons for whoever reads this transcript back.
    """
    return f"{type(exc).__name__} -- {_UNCONFIRMED_DELIVERY}"


def _tx_direction(channel: str, exc) -> str:
    """The transcript `direction` tag for one TX record: the plain channel
    on success, the `-FAILED` variant naming the failure on the other path.

    Encoding attempt-vs-outcome in the direction tag is what lets this
    change stay entirely out of `logging_util.py`: both sinks already take
    `direction` as their first parameter, so nothing about which sink fires,
    or what it receives as content, has to move.
    """
    if exc is None:
        return channel
    return f"{channel}{_FAILED_SUFFIX} {tx_failure_phrase(exc)}"


# WO-CONN-READER-THREAD-DEATH-HONESTY: the marker prefixing every recorded
# reader-thread failure. A typed prefix + the exception's TYPE NAME only --
# never `str(exc)`, which on this code path could carry server bytes from a
# password prompt (`canon/doctrine/secrets-and-credentials.md`). Mirrors
# `guardian.py`'s own `guardian_tick_error:{type(e).__name__}` idiom.
READER_FAILURE_PREFIX = "reader_loop_error:"


class TelnetConnection:
    def __init__(self, host, port, terminal, negotiator, logger=None):
        self.host = host
        self.port = port
        self.terminal = terminal
        self.negotiator = negotiator
        self.logger = logger

        self.lock = threading.Lock()
        self.last_rx = time.monotonic()
        self.rx_count = 0
        self.connected = False
        # `None` until the reader loop dies from an unexpected exception;
        # a clean exit (peer closed, `_stop` set) leaves it `None`. That is
        # what makes "the thread hit a bug" distinguishable from "the link
        # dropped" -- see `_reader_loop`.
        self.reader_failure = None
        # Bumped by every `connect()`. A reader thread captures it at entry
        # and only clears `connected` in its `finally` if the value is still
        # its own -- see `_reader_loop`.
        self._reader_generation = 0

        self._sock = None
        self._reader_thread = None
        self._stop = threading.Event()

    def connect(self, timeout=10):
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._sock.settimeout(None)
        # Clear any failure recorded by a PREVIOUS reader thread before
        # declaring this one live. Without this a reconnect on the same
        # object would come up `connected=True` while still reporting the
        # last death -- the mirror image of the bug this WO fixes, and the
        # kind that reads as "the fault is still happening" long after it
        # stopped. Ordered before `connected = True` so there is no window
        # in which a reader is live and the stale reason is still visible.
        self.reader_failure = None
        # Bump BEFORE starting the thread, so the new reader captures the new
        # generation and any still-draining OLD reader now holds a stale one.
        self._reader_generation += 1
        self.connected = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self):
        """Drain the socket until it closes, this connection is stopped, or
        something in the loop body raises (WO-CONN-READER-THREAD-DEATH-HONESTY).

        **`connected` is cleared in a `finally`, not after the `while`.**
        That placement is the whole fix. Previously `self.connected = False`
        sat below the loop, so it was reached on the two *clean* exits
        (peer closed, `_stop` set) and skipped entirely when the body raised
        -- the thread died and the connection went on advertising itself as
        live (audit `session-iac-audit-20260727.md` I-02, proven by
        execution). `finally` makes the flag track the thread's actual
        liveness on **every** exit path, including ones no one has written
        yet, rather than on the paths someone remembered to enumerate.

        Why that mattered more than a stale boolean: `connected` is what the
        `status` verb reports to every client (`protocol.py`), what the
        disconnect gates test, and -- most consequentially -- what
        `guardian.py::_tick` reads to decide whether to reconnect
        (`if not session.conn.connected: self._maybe_reconnect()`). A
        wrongly-`True` flag disables the component whose entire job is
        noticing the link is gone, so the system cannot recover from the
        failure by the same mechanism the failure breaks.

        **The failure is recorded, not merely survived.** `reader_failure`
        distinguishes "the loop body raised" from an ordinary peer close;
        without it, flipping the flag would make a genuine defect render as
        a routine network drop and the guardian would quietly reconnect
        around it forever -- trading a loud-wrong signal for a quiet-wrong
        one. Following `guardian.py`'s own idiom, it records the exception's
        **type name only, never `str(exc)`**: this loop handles bytes from a
        server that may be mid-password-prompt, and an exception message can
        embed the payload that caused it
        (`canon/doctrine/secrets-and-credentials.md`).

        The exception is re-raised after being recorded so the interpreter's
        own "Exception in thread" traceback still reaches stderr for
        debugging -- recording replaces the *silence*, not the diagnostics.
        `Exception` rather than `BaseException` is caught, so `SystemExit` /
        `KeyboardInterrupt` are not swallowed or relabelled as connection
        faults; the `finally` still clears `connected` for those too.
        """
        generation = self._reader_generation
        try:
            while not self._stop.is_set():
                try:
                    data = self._sock.recv(4096)
                except OSError:
                    break
                if not data:
                    break
                if self.logger:
                    self.logger.log_raw("RX", data)
                clean = self.negotiator.feed(data)
                pending = self.negotiator.pop_pending_output()
                with self.lock:
                    if clean:
                        self.terminal.feed(clean)
                    self.rx_count += len(data)
                    self.last_rx = time.monotonic()
                if pending:
                    self._send_raw(pending)
        except Exception as exc:  # noqa: BLE001 -- recorded and re-raised below
            self.reader_failure = f"{READER_FAILURE_PREFIX}{type(exc).__name__}"
            if self.logger is not None:
                try:
                    # `log_redacted`, not `log_raw`: this note is authored
                    # here and carries no server bytes, and the redaction
                    # sink is the one path guaranteed never to persist
                    # content. A logger that itself raises must not replace
                    # the original failure.
                    self.logger.log_redacted("ERR", f"reader thread died: {self.reader_failure}")
                except Exception:  # noqa: BLE001
                    pass
            raise
        finally:
            # Only clear the flag if this thread is still the CURRENT reader.
            #
            # `close()` does not join the reader thread, so a dying reader can
            # outlive its own connection: close -> reconnect -> the OLD thread
            # finally fires and marks the NEW, live connection down. That race
            # predates this WO -- the original `self.connected = False` sat
            # after the loop with the same exposure -- but Accept #3 asks that
            # the fix not race with the shutdown path, and widening the flag to
            # fire on exception paths too would widen that window rather than
            # leave it as found.
            #
            # A generation check rather than `self._reader_thread is
            # threading.current_thread()`: `connect()` assigns `_reader_thread`
            # AFTER `start()`, so a thread that dies immediately could find the
            # attribute still unset and skip clearing -- reinstating exactly the
            # bug this WO closes. The counter is incremented before `start()`,
            # so it is always already correct when the loop reads it.
            if self._reader_generation == generation:
                self.connected = False

    def _log_tx(self, channel: str, data: bytes, secret: bool, exc):
        """Write the ONE transcript record for a TX that has already
        resolved -- `exc=None` for a completed send, the raised exception
        otherwise.

        The `if secret:` branch below is the module's single redaction
        choke: `send_text()`, `send_bytes()` and `_send_raw()` all reach the
        sinks through here, on both the success and the failure path. It is
        deliberately ONE copy rather than the four the alternative would
        need -- `send_bytes()`'s docstring has always promised it "mirrors
        send_text()'s own redaction contract EXACTLY", and routing both
        through this method makes that true by construction instead of by
        matching copies staying matched.

        `secret` is consumed exactly as handed down; it is never derived,
        re-derived, or second-guessed here (see the module docstring).
        Failure changes only the `direction` TAG -- never which sink fires,
        and never what that sink receives as content.
        """
        if not self.logger:
            return
        direction = _tx_direction(channel, exc)
        if secret:
            self.logger.log_redacted(direction)
        else:
            self.logger.log_raw(direction, data)

    def _send_raw(self, data: bytes):
        """Queued IAC negotiation replies, sent from the reader thread.

        Never `secret` -- these are protocol frames the negotiator
        generated, never operator input, which is why `_log_tx` is called
        with `secret=False` unconditionally here (matching what this method
        has always logged).

        The failure is still SWALLOWED rather than propagated: the reader
        thread must not die because a negotiation reply couldn't go out.
        What changes is that the swallow is no longer SILENT -- before this,
        a failed negotiation reply left the transcript asserting the bytes
        went out and left no trace anywhere that they hadn't.
        """
        if not self._sock:
            return
        try:
            self._sock.sendall(data)
        except OSError as exc:
            self._log_tx(TX_IAC_CHANNEL, data, False, exc)
            return
        self._log_tx(TX_IAC_CHANNEL, data, False, None)

    def send_text(self, text: str, enter: bool = True, secret: bool = False):
        # A non-`str` is refused HERE, at the boundary, with a named type.
        #
        # Before this guard, `None` reached `.encode()` and died as a bare
        # `AttributeError: 'NoneType' object has no attribute 'encode'` from
        # inside the encoder -- four frames below the caller that actually
        # had nothing to send, and rendered to the wire as the useless
        # `internal_error:AttributeError`. Found live: a profile with
        # `allow_register = true` and no handle yet drove the blank-reject
        # retry (`login.py`) into sending `profile.handle`, which was `None`.
        #
        # The daemon renders `internal_error:{type(e).__name__}` and NOTHING
        # else (`daemon.py`), so a precise class name is the one diagnostic
        # channel that is safe by construction -- it carries no payload, no
        # path, and no operator bytes. `SendTextNotAString` says what
        # happened; `AttributeError` says only that something was None
        # somewhere.
        #
        # The message names the offending TYPE, never the value: this is the
        # secret-bearing send path, and a repr of the argument is exactly
        # what `canon/doctrine/secrets-and-credentials.md` forbids.
        #
        # This is the same "fail loud at the send choke" rule the encode
        # comment below states, applied one step earlier.
        if not isinstance(text, str):
            raise SendTextNotAString(
                f"send_text requires str, got {type(text).__name__}"
            )
        # TX: utf-8 strict -- never silent-replace (DECISIONS §B). Surrogates /
        # bad code points must fail loud at the send choke rather than land
        # as U+FFFD on the wire looking like a successful operator action.
        data = text.encode("utf-8")
        if enter:
            data += b"\r\n"
        # BaseException, not OSError: the record must be written for ANY
        # reason this send failed to complete, because the obligation is
        # about bytes that may already be on the wire and that is equally
        # true whatever stopped us. A KeyboardInterrupt landing during a
        # blocked sendall() is a real partial-transmission case, not a
        # theoretical one. Nothing is swallowed -- the bare `raise` re-raises
        # the original exception, traceback intact, so every caller sees
        # exactly what it saw before.
        try:
            self._sock.sendall(data)
        except BaseException as exc:
            self._log_tx(TX_CHANNEL, data, secret, exc)
            raise
        self._log_tx(TX_CHANNEL, data, secret, None)

    def send_bytes(self, data: bytes, secret: bool = False):
        """Exact pass-through -- no text encoding, no auto-appended CRLF
        (unlike send_text()). Used for raw interactive keystrokes (`tw
        attach`), where the caller has already decided the exact wire
        bytes (e.g. a bare CRLF for Enter, an ANSI cursor escape for an
        arrow key).

        `secret`, when True, mirrors send_text()'s own redaction contract
        EXACTLY -- log_redacted() instead of the raw bytes, so a human-
        typed password/PIN/etc typed via `tw attach` never lands in the
        transcript log. The caller (the session's send-choke-point) decides
        `secret` fresh, at the moment THIS call is made, from the CURRENT
        screen; this function trusts whatever it's handed, exactly like
        send_text() already does, and never re-derives it itself.

        That mirroring is now structural rather than a matched pair of
        copies: both methods reach the sinks through the one `_log_tx()`
        choke above, on the failure path as much as the success one. A
        failed SECRET keystroke is redacted exactly like a successful one --
        the failure record carries the marker and no payload."""
        try:
            self._sock.sendall(data)
        except BaseException as exc:
            self._log_tx(TX_CHANNEL, data, secret, exc)
            raise
        self._log_tx(TX_CHANNEL, data, secret, None)

    def force_unblock_sends(self):
        """Wake a peer thread blocked in ``sendall`` / ``recv`` (WO-WEDGED-SEND-FENCE-STICKS).

        The telnet socket is created with ``settimeout(None)`` (blocking, no
        send budget). A wedged ``sendall`` never returns, so an auto-loop
        thread stuck there never reaches ``leave_auto_loop`` in its
        ``finally`` -- and the human wind-down fence stays raised forever.

        This method does **not** clear any control-lock fence or hold: that
        remains the blocked run's own ``finally``. It only shuts the socket
        down so the OS unblocks the waiter; the run then fails the send,
        exits through ``finally``, and releases its generation normally.
        Idempotent. Safe when already closed / never connected.
        """
        sock = self._sock
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.connected = False

    def close(self):
        self._stop.set()
        self.force_unblock_sends()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self.connected = False
