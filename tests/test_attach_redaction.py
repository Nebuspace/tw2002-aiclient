"""Attach keystroke secret redaction (WO-P2-OPS-VERB-F1b).

Proves ``Session.send_raw`` redacts the transcript LOG and ``last_sent``
(→ ``build_response`` ``sent_input``) when the current prompt is a secret
prompt. Ledger / ``record_attach_keystroke`` remain cut (no ``LedgerWriter``
at tip) — STATUS discloses that gap; this suite does not invent a ledger.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time

from tw2002_aiclient.session import protocol
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


# ---------------------------------------------------------------------------
# WO-P4-056 lane B -- whole-surface sweep via the STATUS VERB
# (tw2002_aiclient.session.protocol.dispatch), the exact wire shape the
# product cockpit's status poll actually reads (protocol.py's "status"
# verb additively serves session.tail as `log_tail`, WO-P3-041). Every test
# above proves the LOGGER file / `last_sent` / `build_response()`
# `sent_input` sinks; none of them round-trip a send_raw() secret keystroke
# through the SAME verb the cockpit polls, nor sweep the WHOLE json-dumped
# response rather than one field in isolation -- a field-scoped absence
# assert only proves that ONE field is clean (this project's own WO-P3-041
# Mack finding, cited in this WO's own dispatch). These tests close that
# gap; they do not re-prove anything the tests above already cover.
# ---------------------------------------------------------------------------


class _BareServer:
    """No `control_lock`/`watch_hub` -- protocol.py's status branch reads
    both via `getattr(..., None)`; same shape as
    tests/test_transcript_tail.py's own identically-named fixture (a
    separate class in a separate module -- no cross-file coupling)."""


def test_attach_secret_never_reaches_the_status_verbs_whole_json_response(tmp_path):
    session = _make_session(tmp_path, b"Password:")
    _type_via_send_raw(session, SENTINEL)

    resp = protocol.dispatch(session, "status", {}, _BareServer())
    assert resp["ok"] is True

    # Positive signal first -- the marker actually fired once per typed
    # character, so the absence assert below can't be vacuously true
    # because nothing was ever redacted into this field at all.
    assert resp["log_tail"] == ["<<secret input redacted>>"] * len(SENTINEL)

    # Sentinel absent from the WHOLE status response -- the exact shape the
    # cockpit's status poll / JSON encoder actually sees over the wire, not
    # just the one field a narrower assert might have scoped to.
    dumped = json.dumps(resp)
    assert SENTINEL not in dumped
    session.logger.close()


def test_attach_ordinary_keystrokes_do_reach_the_status_verbs_log_tail(tmp_path):
    """The mandatory asymmetry check, at the status-verb layer this time
    (test_ordinary_command_prompt_is_not_redacted above already proves the
    same asymmetry at the logger layer) -- confirms redaction is a live,
    prompt-driven decision and not a blanket no-op that would make the
    PRESENT/ABSENT pair above trivially true regardless of content."""
    session = _make_session(tmp_path, b"Command [TL=00:00:00]:[1] (?=Help)? :")
    plain = "HELLO"
    _type_via_send_raw(session, plain)

    resp = protocol.dispatch(session, "status", {}, _BareServer())
    # send_raw() is exercised one byte at a time (see _type_via_send_raw),
    # so each keystroke is its own tail entry -- the joined word never
    # appears as one contiguous substring; the exact per-character list
    # below is the real proof that ordinary content reaches the wire.
    assert resp["log_tail"] == [f"human> {ch}" for ch in plain]
    dumped = json.dumps(resp)
    assert all(f"human> {ch}" in dumped for ch in plain)
    assert "redacted" not in dumped
    session.logger.close()
