"""TX record honesty — the transcript must not claim a send that never
completed, nor erase one that may have (WO-AUDIT-TX-RECORD-HONESTY, F6).

Before this work order, `TelnetConnection.send_text()`/`send_bytes()` wrote
the transcript record BEFORE `sendall()`, so a broken pipe left the log
asserting a send that never happened — while `Session.send()`'s LOGS-band
ring, which appends AFTER the connection call returns, correctly recorded
nothing. Two records of the same event, permanently disagreeing.

This is a data-integrity suite, not a logging one. The premise of this
application is that a retrospective AI teacher reads the operator's
transcript as evidence; a transcript asserting a send that never happened
is corrupted evidence, corrupted exactly at the moments things were going
wrong.

**Why "just log after the wire" is NOT the fix, and why these tests are
shaped the way they are.** `sendall()` can raise having ALREADY put bytes on
the wire. That is measured, not assumed — see
`test_real_socket_sendall_can_raise_after_a_genuine_partial_transmission`
below, which drives a real TCP peer and content-verifies the prefix it
received. A log-after-only ordering would erase those bytes from the record.
And the partial case is indistinguishable from a sent-nothing case inside
the except block (same `BrokenPipeError`, same args, no recoverable count),
so no record can honestly state HOW MUCH got through. Hence the shipped
shape: one record per send, written once the outcome is known, with a
distinct `-FAILED` channel tag that states delivery is unconfirmed rather
than claiming or denying it.

**Redaction is the hard fence here.** A failed SECRET send must route to
`log_redacted()` exactly like a successful one — the failure record must
never carry the payload "for diagnostics", and never a byte count (a length
is itself a leak; canon: `canon/doctrine/secrets-and-credentials.md`,
invariant 2). Those are the `_secret_` tests below, and they are the ones
that matter most in this file.
"""

from __future__ import annotations

import socket
import struct
import threading

import pytest

from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.logging_util import TranscriptLogger
from tw2002_aiclient.session.session import Session

from .conftest import FAKE_HOST, FAKE_PORT

# Distinctive so an absence assertion can never pass merely because the
# needle was a common substring of ordinary log furniture.
SECRET = "HUNTER2-TXHONESTY-SENTINEL"
PLAIN = "ORDINARY-TXHONESTY-PAYLOAD"


class _DeadSocket:
    """A socket double whose `sendall` always raises the given exception,
    having transmitted nothing.

    Deterministic stand-in for the real broken pipe proved by
    `test_real_socket_...` below — used for the exhaustive matrix (secret /
    non-secret / IAC / both send methods) where a real network failure would
    add nondeterminism without adding evidence.
    """

    def __init__(self, exc=None):
        self.exc = exc or BrokenPipeError(32, "Broken pipe")
        self.attempts = []

    def sendall(self, data):
        self.attempts.append(data)
        raise self.exc


class _LiveSocket:
    """Succeeds, recording what it was handed."""

    def __init__(self):
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)


def _conn(tmp_path, sock):
    logger = TranscriptLogger(str(tmp_path))
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=logger)
    conn._sock = sock
    return conn, logger


def _read_log(logger):
    logger.close()
    return open(logger.path, encoding="utf-8").read()


def _tx_header_lines(log_text):
    """Just the `[ts] DIRECTION ...` header lines — payload lines never
    start with `[`, matching `test_attach_redaction.py`'s own convention."""
    return [ln for ln in log_text.splitlines() if ln.startswith("[")]


# ---------------------------------------------------------------------------
# The measurement the whole design rests on: a REAL socket, a REAL broken
# pipe, and bytes that genuinely reached the peer anyway.
# ---------------------------------------------------------------------------


def test_real_socket_sendall_can_raise_after_a_genuine_partial_transmission():
    """Establishes by EXECUTION (not from the docs) that `sendall()` raising
    does not mean nothing was transmitted — the fact that makes a
    log-after-only ordering wrong.

    A real TCP peer reads a known prefix, content-verifies it, then hard-RSTs
    (SO_LINGER 0). The sender offers far more than the socket buffers can
    hold, so it is genuinely mid-transmission when the connection dies.
    """
    prefix_target = 128 * 1024
    payload = bytes(range(256)) * 4096  # 1 MiB, positionally distinctive
    payload = payload * 16  # 16 MiB — cannot fit in any socket buffer
    received = {"n": 0, "is_true_prefix": None}

    lsock = socket.socket()
    lsock.bind(("127.0.0.1", 0))
    lsock.listen(1)
    ready = threading.Event()

    def peer():
        conn, _ = lsock.accept()
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
        except OSError:
            pass
        ready.set()
        buf = bytearray()
        while len(buf) < prefix_target:
            chunk = conn.recv(65536)
            if not chunk:
                break
            buf.extend(chunk)
        received["n"] = len(buf)
        received["is_true_prefix"] = bytes(buf) == payload[: len(buf)]
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        conn.close()

    t = threading.Thread(target=peer, daemon=True)
    t.start()
    csock = socket.create_connection(lsock.getsockname(), timeout=10)
    csock.settimeout(None)  # exactly what TelnetConnection.connect() does
    try:
        csock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8192)
    except OSError:
        pass
    ready.wait(5)

    with pytest.raises(OSError) as excinfo:
        csock.sendall(payload)
    t.join(5)
    csock.close()
    lsock.close()

    # (1) bytes REALLY reached the peer, and they are a true prefix of what
    #     was offered — not a coincidence of buffer sizes.
    assert received["n"] > 0
    assert received["is_true_prefix"] is True
    # (2) ...and sendall raised anyway. Log-after-only would have erased
    #     every one of those received["n"] bytes from the record.
    assert isinstance(excinfo.value, OSError)
    # (3) the exception exposes NO recoverable count, so no record can ever
    #     honestly say how much got through. `characters_written` is a
    #     declared-but-unset OSError slot: present in dir(), absent in fact.
    assert getattr(excinfo.value, "characters_written", None) is None


def test_a_successful_sendall_only_proves_local_acceptance_not_peer_delivery():
    """The other bound on what a record may claim: `sendall()` returning
    cleanly does NOT mean the game received anything. This is why the
    SUCCESS tag was left as the plain `TX` it has always been rather than
    reworded into a delivery claim."""
    lsock = socket.socket()
    lsock.bind(("127.0.0.1", 0))
    lsock.listen(1)
    accepted = threading.Event()
    hold = threading.Event()
    peer = {}

    def peer_thread():
        conn, _ = lsock.accept()
        accepted.set()
        hold.wait(5)  # deliberately not reading while the send happens
        peer["entered_recv"] = True
        conn.recv(4096)
        conn.close()

    t = threading.Thread(target=peer_thread, daemon=True)
    t.start()
    csock = socket.create_connection(lsock.getsockname(), timeout=5)
    csock.settimeout(None)
    accepted.wait(5)

    assert csock.sendall(b"PASSWORD-SHAPED\r\n") is None
    # Falsifiable, not merely restated setup: this flag is set from inside
    # the peer the instant it begins reading, so a peer that HAD read before
    # the send returned would fail this assertion.
    assert peer.get("entered_recv") is None

    hold.set()
    t.join(5)
    csock.close()
    lsock.close()


def test_real_broken_pipe_never_leaves_an_unqualified_TX_claim(tmp_path):
    """The headline behavior, end to end on a REAL socket with a REAL broken
    pipe: whatever the transcript says about a send that failed, it must not
    be the same unqualified `TX` record a successful send gets."""
    lsock = socket.socket()
    lsock.bind(("127.0.0.1", 0))
    lsock.listen(1)

    def peer():
        conn, _ = lsock.accept()
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        conn.close()

    t = threading.Thread(target=peer, daemon=True)
    t.start()
    csock = socket.create_connection(lsock.getsockname(), timeout=5)
    csock.settimeout(None)
    t.join(5)

    logger = TranscriptLogger(str(tmp_path))
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=logger)
    conn._sock = csock

    # A dead peer may absorb one write into the local buffer before the RST
    # is observed, so probe with UNIQUE payloads until one genuinely raises;
    # the assertions below are scoped to THAT payload, which makes this loop
    # a setup detail rather than a fuzzy assertion.
    failed_payload = None
    for i in range(10):
        candidate = f"PROBE{i}-{PLAIN}"
        try:
            conn.send_text(candidate, enter=False)
        except OSError:
            failed_payload = candidate
            break
    csock.close()
    lsock.close()

    assert failed_payload is not None, "could not provoke a real broken pipe"
    log_text = _read_log(logger)

    # The failed payload is recorded — its bytes may genuinely have reached
    # the server, so erasing it would be the opposite dishonesty.
    assert failed_payload in log_text
    # ...but NOT under the plain `TX` header a completed send earns.
    # `log_raw` writes `[ts] DIRECTION (n bytes)` then the payload on the
    # next line, so the header for this payload is the line directly above
    # it; each probe payload is unique, so this locates the right record.
    lines = log_text.splitlines()
    idx = lines.index(failed_payload)
    header = lines[idx - 1]
    assert "TX-FAILED" in header, f"failed send got an unqualified header: {header!r}"
    assert "delivery unconfirmed" in header
    assert "BrokenPipeError" in header or "ConnectionResetError" in header


# ---------------------------------------------------------------------------
# REDACTION — the fence. A failed secret send must be exactly as sealed as a
# successful one.
# ---------------------------------------------------------------------------


def test_secret_send_that_fails_never_writes_the_payload_into_the_record(tmp_path):
    conn, logger = _conn(tmp_path, _DeadSocket())
    with pytest.raises(BrokenPipeError):
        conn.send_text(SECRET, secret=True)
    log_text = _read_log(logger)

    # Positive signal first, so the absence assertion below cannot pass
    # vacuously by nothing having been recorded at all.
    assert "TX-FAILED" in log_text
    assert "secret input redacted" in log_text

    assert SECRET not in log_text
    assert SECRET.encode() not in open(logger.path, "rb").read()


def test_secret_send_that_fails_leaks_no_byte_count(tmp_path):
    """A length is itself a leak (canon invariant 2). The failure record for
    a secret send must go through `log_redacted()`, which emits no count —
    NOT through `log_raw()`, which always emits `(N bytes)`."""
    conn, logger = _conn(tmp_path, _DeadSocket())
    with pytest.raises(BrokenPipeError):
        conn.send_text(SECRET, secret=True)
    log_text = _read_log(logger)

    assert "TX-FAILED" in log_text  # non-vacuity: a record WAS written
    # `log_raw` ALWAYS emits `(N bytes)`; `log_redacted` never does. Absence
    # of the marker is therefore positive proof the redacted sink was the
    # one that fired. (Deliberately not asserting the absence of the literal
    # count: a two-digit length collides with the timestamp's own digits and
    # would make this test flaky rather than strict.)
    assert "bytes)" not in log_text


def test_secret_send_bytes_that_fails_is_redacted_exactly_like_send_text(tmp_path):
    """`send_bytes()`'s docstring promises it mirrors `send_text()`'s
    redaction contract EXACTLY. That promise has to survive the failure path
    too — this is the `tw attach` keystroke channel, where a human-typed
    password reaches the wire."""
    conn, logger = _conn(tmp_path, _DeadSocket())
    with pytest.raises(BrokenPipeError):
        conn.send_bytes(SECRET.encode(), secret=True)
    log_text = _read_log(logger)

    assert "TX-FAILED" in log_text
    assert "secret input redacted" in log_text
    assert SECRET not in log_text
    assert "bytes)" not in log_text


def test_failure_record_carries_the_exception_TYPE_never_its_MESSAGE(tmp_path):
    """An exception's message is not structurally incapable of carrying
    operator input or server payload; its class name is. Same reasoning
    `Session.reconnect()` and `watch.WatchHub` already document."""

    class _LeakyError(OSError):
        def __str__(self):
            return f"connection died while sending {SECRET}"

    conn, logger = _conn(tmp_path, _DeadSocket(_LeakyError()))
    with pytest.raises(_LeakyError):
        conn.send_text(SECRET, secret=True)
    log_text = _read_log(logger)

    assert "_LeakyError" in log_text  # the TYPE is recorded
    assert SECRET not in log_text  # the MESSAGE is not
    assert "connection died while sending" not in log_text


def test_secret_session_send_failure_puts_no_cleartext_on_the_logs_band(tmp_path):
    """The LOGS-band ring is the operator-visible transcript surface and is
    served on the wire as `log_tail`. A failed secret send must be as sealed
    there as in the log file."""
    session = Session(FAKE_HOST, FAKE_PORT, None, str(tmp_path))
    session.conn._sock = _DeadSocket()
    with pytest.raises(BrokenPipeError):
        session.send(SECRET, secret=True)

    snapshot = session.tail.snapshot()
    assert snapshot, "the failure was not recorded on the LOGS band at all"
    joined = "\n".join(snapshot)
    assert "secret input redacted" in joined  # non-vacuity
    assert "send failed" in joined
    assert SECRET not in joined
    session.logger.close()


# ---------------------------------------------------------------------------
# The two surfaces must now agree — the actual F6 defect.
# ---------------------------------------------------------------------------


def test_failed_send_is_recorded_by_BOTH_the_log_and_the_logs_band(tmp_path):
    """Pre-fix, the log file asserted the send while the LOGS-band ring
    recorded nothing — two records of one event, permanently disagreeing.
    Both must now describe the same failed send."""
    session = Session(FAKE_HOST, FAKE_PORT, None, str(tmp_path))
    session.conn._sock = _DeadSocket()
    with pytest.raises(BrokenPipeError):
        session.send(PLAIN)

    joined_tail = "\n".join(session.tail.snapshot())
    log_text = _read_log(session.logger)

    assert "TX-FAILED" in log_text
    assert "delivery unconfirmed" in log_text
    assert "send failed" in joined_tail
    assert "BrokenPipeError" in joined_tail
    # Neither surface erased WHAT was attempted — those bytes may be on the
    # wire (see the real-socket partial-transmission test above).
    assert PLAIN in log_text
    assert PLAIN in joined_tail


def test_both_surfaces_name_the_failure_with_the_same_shared_wording(tmp_path):
    """The two records are built from one `tx_failure_phrase()` rather than
    two hand-written copies, so they cannot drift apart again."""
    session = Session(FAKE_HOST, FAKE_PORT, None, str(tmp_path))
    session.conn._sock = _DeadSocket()
    with pytest.raises(BrokenPipeError):
        session.send(PLAIN)

    joined_tail = "\n".join(session.tail.snapshot())
    log_text = _read_log(session.logger)
    phrase = "BrokenPipeError -- attempted, delivery unconfirmed"
    assert phrase in log_text
    assert phrase in joined_tail


def test_failed_send_leaves_last_sent_describing_the_last_COMPLETED_send(tmp_path):
    """Deliberate NON-change, pinned so a later edit can't quietly flip it:
    `last_sent` is current-state, not history. After a failure it keeps
    naming the last send that actually completed — which stays true — while
    the transcript surfaces carry the record of the attempt."""
    session = Session(FAKE_HOST, FAKE_PORT, None, str(tmp_path))
    session.conn._sock = _LiveSocket()
    session.send("FIRST-OK")
    assert session.last_sent == "FIRST-OK"
    stamp = session.last_sent_ts

    session.conn._sock = _DeadSocket()
    with pytest.raises(BrokenPipeError):
        session.send(PLAIN)

    assert session.last_sent == "FIRST-OK"
    assert session.last_sent_ts == stamp
    session.logger.close()


# ---------------------------------------------------------------------------
# The success path must be untouched — otherwise this fix is a format churn
# wearing an honesty costume.
# ---------------------------------------------------------------------------


def test_successful_send_record_is_unchanged_and_carries_no_failure_tag(tmp_path):
    conn, logger = _conn(tmp_path, _LiveSocket())
    conn.send_text(PLAIN, enter=False)
    log_text = _read_log(logger)

    headers = _tx_header_lines(log_text)
    assert len(headers) == 1
    assert headers[0].endswith(f"TX ({len(PLAIN)} bytes)")
    assert "FAILED" not in log_text
    assert log_text.splitlines()[1] == PLAIN


def test_successful_secret_send_record_is_unchanged(tmp_path):
    conn, logger = _conn(tmp_path, _LiveSocket())
    conn.send_text(SECRET, secret=True)
    log_text = _read_log(logger)

    headers = _tx_header_lines(log_text)
    assert len(headers) == 1
    assert headers[0].endswith("TX <<secret input redacted>>")
    assert SECRET not in log_text


def test_a_send_is_recorded_only_after_the_wire_call_resolves(tmp_path):
    """The ordering property itself, observed directly rather than inferred:
    at the instant `sendall` is executing, nothing has been written yet."""
    logger = TranscriptLogger(str(tmp_path))
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=logger)
    observed = {}

    class _ObservingSocket:
        def sendall(self, data):
            observed["log_during_send"] = open(logger.path, encoding="utf-8").read()

    conn._sock = _ObservingSocket()
    conn.send_text(PLAIN, enter=False)
    after = _read_log(logger)

    assert observed["log_during_send"] == ""
    assert PLAIN in after


# ---------------------------------------------------------------------------
# Defect-class sweep result: the IAC channel had the SAME defect plus a
# silent swallow. Not named in the work order; found by sweeping.
# ---------------------------------------------------------------------------


def test_failed_IAC_negotiation_reply_no_longer_claims_it_went_out(tmp_path):
    """`_send_raw()` logged `TX-IAC` before the wire AND swallowed the
    OSError, so a failed negotiation reply left the transcript asserting
    bytes that never went and left no trace anywhere that they hadn't."""
    conn, logger = _conn(tmp_path, _DeadSocket())
    conn._send_raw(b"\xff\xfb\x18")  # IAC WILL TERMINAL-TYPE
    log_text = _read_log(logger)

    assert "TX-IAC-FAILED" in log_text
    assert "delivery unconfirmed" in log_text


def test_failed_IAC_negotiation_reply_is_still_swallowed_not_propagated(tmp_path):
    """The swallow is deliberate and preserved — the reader thread must not
    die because a negotiation reply couldn't go out. Only the SILENCE was
    the defect."""
    conn, logger = _conn(tmp_path, _DeadSocket())
    conn._send_raw(b"\xff\xfb\x18")  # must not raise
    logger.close()


def test_successful_IAC_negotiation_reply_record_is_unchanged(tmp_path):
    conn, logger = _conn(tmp_path, _LiveSocket())
    conn._send_raw(b"\xff\xfb\x18")
    log_text = _read_log(logger)

    headers = _tx_header_lines(log_text)
    assert len(headers) == 1
    assert headers[0].endswith("TX-IAC (3 bytes)")
    assert "FAILED" not in log_text


# ---------------------------------------------------------------------------
# Nothing is swallowed on the caller-facing send paths.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("secret", [False, True])
def test_send_text_re_raises_the_original_exception_unchanged(tmp_path, secret):
    original = ConnectionResetError(54, "Connection reset by peer")
    conn, logger = _conn(tmp_path, _DeadSocket(original))
    with pytest.raises(ConnectionResetError) as excinfo:
        conn.send_text(PLAIN, secret=secret)
    assert excinfo.value is original
    logger.close()


@pytest.mark.parametrize("secret", [False, True])
def test_send_bytes_re_raises_the_original_exception_unchanged(tmp_path, secret):
    original = ConnectionResetError(54, "Connection reset by peer")
    conn, logger = _conn(tmp_path, _DeadSocket(original))
    with pytest.raises(ConnectionResetError) as excinfo:
        conn.send_bytes(PLAIN.encode(), secret=secret)
    assert excinfo.value is original
    logger.close()


def test_a_non_OSError_failure_is_also_recorded_and_re_raised(tmp_path):
    """The obligation is about bytes that may be on the wire, which is
    equally true whatever stopped the send — hence the deliberately broad
    except. A KeyboardInterrupt during a blocked sendall is the real case
    this covers."""
    conn, logger = _conn(tmp_path, _DeadSocket(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        conn.send_text(PLAIN)
    log_text = _read_log(logger)
    assert "TX-FAILED KeyboardInterrupt" in log_text


def test_send_with_no_logger_still_re_raises_and_never_crashes(tmp_path):
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=None)
    conn._sock = _DeadSocket()
    with pytest.raises(BrokenPipeError):
        conn.send_text(PLAIN, secret=True)
