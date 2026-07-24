"""TelnetConnection unit tests — no network.

`send_bytes(secret=...)` mirrors `send_text(secret=...)`'s redaction
contract. Proved against the real TelnetConnection + TranscriptLogger.
"""

from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.logging_util import TranscriptLogger

from .conftest import FAKE_HOST, FAKE_PORT

SENTINEL = b"HUNTER2SENTINEL"


class _StubSocket:
    """Discards every byte instead of touching a real network socket."""

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
    conn, logger = _make_conn(tmp_path)
    conn.send_bytes(SENTINEL, secret=True)
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL.decode() not in content
    assert "secret input redacted" in content
    assert SENTINEL not in open(logger.path, "rb").read()


def test_send_bytes_secret_true_still_sends_the_real_bytes_over_the_wire():
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=None)
    conn._sock = _StubSocket()
    conn.send_bytes(SENTINEL, secret=True)
    assert conn._sock.sent_bytes == [SENTINEL]


def test_send_text_secret_true_redacts_the_log_line(tmp_path):
    conn, logger = _make_conn(tmp_path)
    conn.send_text("hunter2", secret=True)
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "hunter2" not in content
    assert "secret input redacted" in content


def test_send_text_appends_crlf_by_default():
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=None)
    conn._sock = _StubSocket()
    conn.send_text("A", enter=True)
    assert conn._sock.sent_bytes == [b"A\r\n"]


def test_send_text_enter_false_sends_exact_bytes():
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=None)
    conn._sock = _StubSocket()
    conn.send_text("A", enter=False)
    assert conn._sock.sent_bytes == [b"A"]


def test_send_bytes_with_no_logger_never_raises():
    conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=None)
    conn._sock = _StubSocket()
    conn.send_bytes(SENTINEL, secret=True)
