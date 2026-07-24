"""WO-P2-OPS-VERB-A — CLI wire for ``tw screen`` / ``tw stop``.

Protocol already handles both verbs; this slice proves the CLI parser +
``send_request`` path and a FakeSession protocol smoke — no live daemon.
"""

from __future__ import annotations

import json
from argparse import Namespace
from unittest.mock import patch

from tw2002_aiclient.session import cli, protocol


class _FakeConn:
    connected = True


class FakeSession:
    """Minimal session for ``protocol.dispatch(..., \"screen\"|\"stop\")``."""

    def __init__(self, rows):
        self._rows = list(rows)
        self.conn = _FakeConn()
        self.last_sent = None
        self.host = "127.0.0.1"
        self.port = 23
        self.name = "test"

    def render(self):
        return list(self._rows)

    def render_raw(self):
        return list(self._rows)

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self._rows)


class FakeServer:
    def __init__(self):
        self.stop_called = False
        self.control_lock = None

    def request_stop(self):
        self.stop_called = True


def test_parser_lists_screen_and_stop():
    parser = cli.build_parser()
    help_text = parser.format_help()
    assert "screen" in help_text and "stop" in help_text
    screen = parser.parse_args(["screen", "--raw", "--compact", "--run-dir", "run/ona"])
    assert screen.func is cli.cmd_screen
    assert screen.raw is True
    assert screen.compact is True
    assert screen.run_dir == "run/ona"
    stop = parser.parse_args(["stop", "--json"])
    assert stop.func is cli.cmd_stop
    assert stop.json is True


def test_cmd_screen_forwards_raw_and_run_dir(monkeypatch, capsys, tmp_path):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        seen["run_dir"] = run_dir
        return {
            "ok": True,
            "screen": ["Command [TL=00:00:00]:[1] (?=Help)? :"],
            "prompt": "Command [TL=00:00:00]:[1] (?=Help)? :",
            "classification": "main_command",
        }

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = Namespace(raw=True, compact=False, json=False, run_dir=str(tmp_path / "ona"))
    rc = cli.cmd_screen(args)
    assert rc == 0
    assert seen["verb"] == "screen"
    assert seen["args"] == {"raw": True}
    assert seen["run_dir"] == tmp_path / "ona"
    out = capsys.readouterr().out
    assert "Command [TL=00:00:00]:[1] (?=Help)? :" in out
    assert "class: main_command" in out


def test_cmd_screen_compact_omits_footer(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "send_request",
        lambda *a, **k: {
            "ok": True,
            "screen": ["hi"],
            "prompt": "hi",
            "classification": "unknown",
        },
    )
    args = Namespace(raw=False, compact=True, json=False, run_dir=None)
    assert cli.cmd_screen(args) == 0
    out = capsys.readouterr().out
    assert out.strip() == "hi"
    assert "class:" not in out


def test_cmd_stop_when_daemon_down(capsys, tmp_path):
    args = Namespace(json=False, run_dir=str(tmp_path / "empty"))
    with patch.object(cli, "daemon_alive", return_value=False):
        rc = cli.cmd_stop(args)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "daemon not running"


def test_cmd_stop_when_daemon_down_json(capsys, tmp_path):
    args = Namespace(json=True, run_dir=str(tmp_path / "empty"))
    with patch.object(cli, "daemon_alive", return_value=False):
        rc = cli.cmd_stop(args)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["daemon_running"] is False
    assert "empty" in payload["run_dir"].replace("\\", "/")


def test_cmd_stop_sends_stop_verb(monkeypatch, capsys, tmp_path):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        seen["run_dir"] = run_dir
        return {"ok": True, "stopping": True}

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: True)
    monkeypatch.setattr(cli, "send_request", fake_send)
    args = Namespace(json=True, run_dir=str(tmp_path / "run"))
    rc = cli.cmd_stop(args)
    assert rc == 0
    assert seen["verb"] == "stop"
    assert seen["args"] == {}
    assert seen["run_dir"] == tmp_path / "run"
    assert json.loads(capsys.readouterr().out)["stopping"] is True


def test_protocol_screen_and_stop_fake_session():
    session = FakeSession(["Command [TL=00:00:00]:[1] (?=Help)? :"])
    server = FakeServer()
    screen = protocol.dispatch(session, "screen", {}, server)
    assert screen["ok"] is True
    assert screen["screen"] == ["Command [TL=00:00:00]:[1] (?=Help)? :"]
    assert "classification" in screen
    assert server.stop_called is False

    raw = protocol.dispatch(session, "screen", {"raw": True}, server)
    assert raw["ok"] is True
    assert raw["screen"] == session.render_raw()

    stop = protocol.dispatch(session, "stop", {}, server)
    assert stop == {"ok": True, "stopping": True}
    assert server.stop_called is True
