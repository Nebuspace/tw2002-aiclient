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

        self._sock = None
        self._reader_thread = None
        self._stop = threading.Event()

    def connect(self, timeout=10):
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._sock.settimeout(None)
        self.connected = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self):
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
        data = text.encode("utf-8", errors="replace")
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

    def close(self):
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
        self.connected = False
