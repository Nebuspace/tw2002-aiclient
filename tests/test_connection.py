"""TelnetConnection (twclient/connection.py) unit tests -- no network.
`send_bytes(secret=...)` (WO-CLEANPREEMPT secret sub-diff) mirrors
`send_text(secret=...)`'s existing redaction contract exactly -- these
tests prove the log-gate directly against the REAL TelnetConnection +
TranscriptLogger, isolated from Session/daemon.py wiring (that end-to-end
proof, plus the "attach path decides secret from the CURRENT screen"
mechanics, lives in tests/test_session.py and tests/test_attach_redaction.py)."""

from twclient.connection import TelnetConnection
from twclient.logging_util import TranscriptLogger

from .conftest import FAKE_HOST, FAKE_PORT

SENTINEL = b"HUNTER2SENTINEL"


class _StubSocket:
    """Discards every byte instead of touching a real network socket --
    same convention as tests/test_login_redaction.py's own _StubSocket."""

    def __init__(self):
        self.sent_bytes = []

    def sendall(self, data):
        self.sent_bytes.append(data)


def _make_conn(tmp_path):
    logger = TranscriptLogger(str(tmp_path))
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=logger)
    conn._sock = _StubSocket()
    return conn, logger


def test_send_bytes_secret_false_logs_raw_bytes(tmp_path):
    conn, logger = _make_conn(tmp_path)
    conn.send_bytes(b"ordinary-key")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "ordinary-key" in content


def test_send_bytes_secret_true_redacts_the_log_line(tmp_path):
    """The core WO-CLEANPREEMPT secret sub-diff fix: `secret=True` routes
    through `log_redacted()` instead of `log_raw()`, exactly mirroring
    `send_text(secret=True)`'s own contract -- the sentinel never
    appears in the transcript."""
    conn, logger = _make_conn(tmp_path)
    conn.send_bytes(SENTINEL, secret=True)
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL.decode() not in content
    assert "secret input redacted" in content
    # Also never present as a raw-bytes read -- not just a decode-level miss.
    assert SENTINEL not in open(logger.path, "rb").read()


def test_send_bytes_secret_true_still_sends_the_real_bytes_over_the_wire():
    """Redaction is a LOGGING concern only -- the actual bytes still
    reach the socket unmodified; only the transcript is protected."""
    logger = None
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=logger)
    conn._sock = _StubSocket()
    conn.send_bytes(SENTINEL, secret=True)
    assert conn._sock.sent_bytes == [SENTINEL]


def test_falsification_send_bytes_without_the_secret_gate_would_leak_RED(tmp_path):
    """Sensitivity/falsification control: simulates the pre-fix behavior
    (secret ignored, always log_raw) to prove the green result above is a
    real signal, not a check that could never fail."""
    logger = TranscriptLogger(str(tmp_path))
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=logger)
    conn._sock = _StubSocket()

    # The exact pre-fix body: secret is accepted but never consulted.
    def _leaky_send_bytes(self, data, secret=False):
        if self.logger:
            self.logger.log_raw("TX", data)
        self._sock.sendall(data)

    _leaky_send_bytes(conn, SENTINEL, secret=True)
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL.decode() in content  # RED: the leak is caught by this same test shape


def test_send_bytes_with_no_logger_never_raises():
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=None)
    conn._sock = _StubSocket()
    conn.send_bytes(SENTINEL, secret=True)  # must not raise
