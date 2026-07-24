"""Attach keystroke secret redaction (WO-P2-OPS-VERB-F1b).

Proves ``Session.send_raw`` redacts the transcript LOG and ``last_sent``
(→ ``build_response`` ``sent_input``) when the current prompt is a secret
prompt. Ledger / ``record_attach_keystroke`` remain cut (no ``LedgerWriter``
at tip) — STATUS discloses that gap; this suite does not invent a ledger.
"""

from __future__ import annotations

import subprocess
import threading
import time

from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.protocol import build_response
from tw2002_aiclient.session.session import Session

from .conftest import FAKE_HOST, FAKE_PORT

SENTINEL = "HUNTER2SENTINEL"


class _StubSocket:
    def sendall(self, data):
        pass


def _grep_a_contains(path, needle):
    r = subprocess.run(
        ["grep", "-a", "-F", "--", needle, str(path)],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def _make_session(tmp_path, screen_bytes):
    session = Session(FAKE_HOST, FAKE_PORT, None, str(tmp_path))
    session.conn._sock = _StubSocket()
    session.terminal.feed(screen_bytes)
    return session


def _typed_content_from_log(log_content):
    return "".join(line for line in log_content.splitlines() if not line.startswith("["))


def _type_via_send_raw(session, text, control_lock=None):
    for ch in text:
        session.send_raw(ch.encode("latin-1"), control_lock=control_lock)


def test_password_prompt_sentinel_never_leaks_in_log_or_last_sent(tmp_path):
    session = _make_session(tmp_path, b"Password:")
    _type_via_send_raw(session, SENTINEL)
    session.logger.close()

    log_content = open(session.logger.path, encoding="utf-8").read()
    assert SENTINEL not in log_content
    assert _typed_content_from_log(log_content) == ""
    assert log_content.count("secret input redacted") == len(SENTINEL)
    assert SENTINEL.encode() not in open(session.logger.path, "rb").read()
    assert _grep_a_contains(session.logger.path, SENTINEL) is False
    assert session.last_sent == "<redacted>"
    assert session.last_sent_secret is True
    assert build_response(session)["sent_input"] == "<redacted>"


def test_falsification_removing_log_gate_lets_sentinel_leak(tmp_path, monkeypatch):
    def _leaky_send_bytes(self, data, secret=False):
        if self.logger:
            self.logger.log_raw("TX", data)
        self._sock.sendall(data)

    monkeypatch.setattr(TelnetConnection, "send_bytes", _leaky_send_bytes)
    session = _make_session(tmp_path, b"Password:")
    _type_via_send_raw(session, SENTINEL)
    session.logger.close()
    log_content = open(session.logger.path, encoding="utf-8").read()
    assert _typed_content_from_log(log_content) == SENTINEL


def test_pin_prompt_sentinel_never_leaks(tmp_path):
    session = _make_session(tmp_path, b"Enter PIN:")
    pin = "13375ENTINEL"
    _type_via_send_raw(session, pin)
    session.logger.close()
    log_content = open(session.logger.path, encoding="utf-8").read()
    assert pin not in log_content
    assert session.last_sent == "<redacted>"


def test_ordinary_command_prompt_is_not_redacted(tmp_path):
    session = _make_session(tmp_path, b"Command [TL=00:00:00]:[1] (?=Help)? :")
    plain = "HELLO"
    _type_via_send_raw(session, plain)
    session.logger.close()
    log_content = open(session.logger.path, encoding="utf-8").read()
    assert _typed_content_from_log(log_content) == plain
    assert session.last_sent == "O"  # last char
    assert session.last_sent_secret is False


def test_documented_residual_no_secret_keyword_not_redacted(tmp_path):
    session = _make_session(tmp_path, b"Speak, friend, and enter:")
    answer = "MELLON"
    _type_via_send_raw(session, answer)
    session.logger.close()
    log_content = open(session.logger.path, encoding="utf-8").read()
    assert _typed_content_from_log(log_content) == answer


def test_staleness_secret_during_fence_wait_still_redacted(tmp_path):
    session = _make_session(tmp_path, b"Command [TL=00:00:00]:[1] (?=Help)? :")
    lock = ControlLock()
    lock.acquire_driver()
    lock.take_human()
    result = {}

    def send_call():
        session.send_raw(SENTINEL[0].encode("latin-1"), control_lock=lock)
        result["done"] = True

    t = threading.Thread(target=send_call)
    t.start()
    time.sleep(0.15)
    assert "done" not in result
    session.terminal.feed(b"\x1b[2J\x1b[HPassword:")
    lock.release_driver()
    t.join(timeout=2.0)
    assert result.get("done") is True
    session.logger.close()
    log_content = open(session.logger.path, encoding="utf-8").read()
    assert SENTINEL[0] not in _typed_content_from_log(log_content)
    assert "secret input redacted" in log_content
    assert session.last_sent == "<redacted>"
