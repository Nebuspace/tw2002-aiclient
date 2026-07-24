"""WO-P2-OPS-VERB-C — ``tw history`` (session ring). ``tw state`` deferred."""

from __future__ import annotations

from argparse import Namespace

from tw2002_aiclient.session import cli, protocol


class _FakeConn:
    connected = True


class FakeSession:
    def __init__(self):
        self.history = []
        self.conn = _FakeConn()
        self.host = "127.0.0.1"
        self.port = 23
        self.name = "test"

    def render(self):
        return ["x"]

    def render_text(self, rows=None):
        return "x"


class FakeServer:
    control_lock = None


def test_parser_lists_history():
    parser = cli.build_parser()
    assert "history" in parser.format_help()
    args = parser.parse_args(["history", "--n", "5", "--json"])
    assert args.func is cli.cmd_history
    assert args.n == 5


def test_cmd_history_forwards_n(monkeypatch, tmp_path):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        seen["run_dir"] = run_dir
        return {"ok": True, "history": []}

    monkeypatch.setattr(cli, "send_request", fake_send)
    rc = cli.cmd_history(Namespace(n=3, json=True, run_dir=str(tmp_path / "r")))
    assert rc == 0
    assert seen == {"verb": "history", "args": {"n": 3}, "run_dir": tmp_path / "r"}


def test_protocol_history_returns_tail():
    session = FakeSession()
    session.history = [
        {"verb": "do", "args": {"input": "<redacted>"}, "prompt": "Password?"},
        {"verb": "do", "args": {"input": "d"}, "prompt": "Command"},
        {"verb": "read", "args": {}, "prompt": "Command"},
    ]
    resp = protocol.dispatch(session, "history", {"n": 2}, FakeServer())
    assert resp["ok"] is True
    assert len(resp["history"]) == 2
    assert resp["history"][0]["verb"] == "do"
    assert resp["history"][0]["args"]["input"] == "d"
    # secret redaction preserved from record_history callers
    assert session.history[0]["args"]["input"] == "<redacted>"


def test_protocol_state_still_unknown():
    """state_parser not ported — do not invent a fake state verb."""
    resp = protocol.dispatch(FakeSession(), "state", {}, FakeServer())
    assert resp == {"ok": False, "error": "unknown_verb:state"}
