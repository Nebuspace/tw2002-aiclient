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


def test_rx_ordinary_chunk_logs_raw(tmp_path):
    conn, logger = _make_conn(tmp_path)
    conn._log_rx(b"Command [TL=100]:")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "Command [TL=100]:" in content
    assert "RX" in content
    assert "secret input redacted" not in content


def test_rx_password_anchor_redacts_without_secret_pending(tmp_path):
    conn, logger = _make_conn(tmp_path)
    assert conn._redact_rx is False
    conn._log_rx(b"Enter your password:\r\n")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "Enter your password" not in content
    assert "RX <<secret input redacted>>" in content


def test_rx_after_secret_tx_redacts_echo_without_password_word(tmp_path):
    conn, logger = _make_conn(tmp_path)
    conn.send_bytes(SENTINEL, secret=True)
    assert conn._redact_rx is True
    conn._log_rx(SENTINEL)  # echoing server — no "password" word
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL.decode() not in content
    assert content.count("secret input redacted") >= 2  # TX + RX
    assert SENTINEL not in open(logger.path, "rb").read()


def test_rx_clears_after_non_secret_operator_tx(tmp_path):
    conn, logger = _make_conn(tmp_path)
    conn.send_bytes(SENTINEL, secret=True)
    assert conn._redact_rx is True
    conn.send_bytes(b"D")  # ordinary keystroke clears the window
    assert conn._redact_rx is False
    conn._log_rx(b"Sector 1\r\n")
    logger.close()
    content = open(logger.path, encoding="utf-8").read()
    assert "Sector 1" in content


def test_tx_iac_does_not_clear_rx_redact_window(tmp_path):
    conn, logger = _make_conn(tmp_path)
    conn.send_bytes(SENTINEL, secret=True)
    assert conn._redact_rx is True
    conn._send_raw(b"\xff\xfc\x01")  # IAC negotiation reply
    assert conn._redact_rx is True
    conn._log_rx(SENTINEL)
    logger.close()
    assert SENTINEL.decode() not in open(logger.path, encoding="utf-8").read()
