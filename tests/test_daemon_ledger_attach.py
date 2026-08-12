"""WO-DAEMON-LEDGER-WRITER-ATTACH — do/send/attach append Trace-Ledger rows."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tw2002_aiclient.ledger import REDACTED, LedgerWriter, read_entries
from tw2002_aiclient.session import protocol
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.session import Session, VALID_SENDERS

from .conftest import FAKE_HOST, FAKE_PORT


class _StubSocket:
    def sendall(self, data):
        pass


def _server(session, tmp_path: Path):
    lock = ControlLock()
    return SimpleNamespace(
        session=session,
        control_lock=lock,
        ledger=LedgerWriter(path=tmp_path / "ledger.jsonl"),
        watch_hub=None,
        autoloop=None,
    )


def _session(tmp_path: Path, screen: bytes = b"Command [TL=40]:") -> Session:
    session = Session(FAKE_HOST, FAKE_PORT, None, str(tmp_path / "logs"))
    session.conn._sock = _StubSocket()
    session.terminal.feed(screen)
    return session


def test_send_verb_appends_app_actor_row(tmp_path: Path) -> None:
    session = _session(tmp_path)
    server = _server(session, tmp_path)
    resp = protocol.dispatch(session, "send", {"input": "p"}, server)
    assert resp["ok"] is True
    rows = read_entries(tmp_path / "ledger.jsonl")
    assert len(rows) == 1
    assert rows[0]["actor"] == "app"
    assert rows[0]["actor"] in VALID_SENDERS
    assert rows[0]["input"] == "p"
    assert rows[0]["session_id"] == session.session_id


def test_send_secret_redacts_ledger_input(tmp_path: Path) -> None:
    session = _session(tmp_path, b"Password:")
    server = _server(session, tmp_path)
    protocol.dispatch(
        session, "send", {"input": "hunter2", "secret": True}, server
    )
    rows = read_entries(tmp_path / "ledger.jsonl")
    assert rows[0]["input"] == REDACTED
    assert rows[0]["actor"] == "app"
    assert "hunter2" not in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")


def test_record_attach_keystroke_human_actor(tmp_path: Path) -> None:
    session = _session(tmp_path)
    server = _server(session, tmp_path)
    pre = session.render_text(session.render())
    session.send_raw(b"d", control_lock=server.control_lock, sender="human")
    protocol.record_attach_keystroke(
        server, session, pre, session.last_sent, session.last_sent_secret
    )
    rows = read_entries(tmp_path / "ledger.jsonl")
    assert len(rows) == 1
    assert rows[0]["actor"] == "human"
    assert rows[0]["input"] == "d"


def test_record_attach_secret_redacts(tmp_path: Path) -> None:
    session = _session(tmp_path, b"Password:")
    server = _server(session, tmp_path)
    pre = session.render_text(session.render())
    session.send_raw(b"x", control_lock=server.control_lock, sender="human")
    protocol.record_attach_keystroke(
        server, session, pre, session.last_sent, session.last_sent_secret
    )
    rows = read_entries(tmp_path / "ledger.jsonl")
    assert rows[0]["input"] == REDACTED
    assert rows[0]["actor"] == "human"


def test_no_ai_actor_ever_written(tmp_path: Path) -> None:
    """Mutation pin: _record_ledger refuses ai attribution."""
    session = _session(tmp_path)
    server = _server(session, tmp_path)
    protocol._record_ledger(
        server,
        session,
        "pre",
        "x",
        secret=False,
        resp={"screen": ["Command:"], "classification": "main_command"},
        actor="ai",
    )
    assert read_entries(tmp_path / "ledger.jsonl") == []


def test_dev_actor_is_attributed(tmp_path: Path) -> None:
    """WO-BUILD-LEDGER-DEV-SENDER-ATTRIBUTION: sacrificial dev rows land."""
    session = _session(tmp_path)
    server = _server(session, tmp_path)
    protocol._record_ledger(
        server,
        session,
        "pre",
        "d",
        secret=False,
        resp={"screen": ["Command:"], "classification": "main_command"},
        actor="dev",
    )
    rows = read_entries(tmp_path / "ledger.jsonl")
    assert len(rows) == 1
    assert rows[0]["actor"] == "dev"
    assert rows[0]["input"] == "d"


def test_daemon_imports_record_attach_and_constructs_ledger() -> None:
    src = Path(__file__).resolve().parents[1] / "tw2002_aiclient" / "session" / "daemon.py"
    text = src.read_text(encoding="utf-8")
    assert "from ..ledger import LedgerWriter" in text
    assert "record_attach_keystroke" in text
    assert "ledger = LedgerWriter()" in text
    assert "server.ledger = ledger" in text
    assert "ledger=ledger" in text  # guardian shares same writer
    assert "LedgerWriter / record_attach_keystroke deferred" not in text
