"""WO-P2-OPS-VERB-C — ``tw history`` (session ring). The ``state`` protocol
verb landed later, in WO-P2-G4-X1; this file keeps only the "it is not a
stub" pin, and ``tests/test_state_sector_read.py`` owns the read's contract.
There is still no ``tw state`` CLI subcommand — X1 deliberately added no CLI
surface (the daemon verb is the consumer-facing contract)."""

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


def test_protocol_state_is_a_real_read_not_a_stub():
    """Was ``test_protocol_state_still_unknown`` — "state_parser not ported,
    do not invent a fake state verb". WO-P2-G4-X1 ported it, so the pin
    changes from "the verb does not exist" to "the verb does not FAKE it",
    which is the same intent against a landed implementation.

    Two halves, and the second is the one the original was guarding. This
    file's ``FakeSession`` renders the screen ``"x"``, which carries no
    current-sector claim at all — so a stub returning a plausible number
    would show up here immediately. Full coverage of the read itself lives
    in ``tests/test_state_sector_read.py``.
    """
    resp = protocol.dispatch(FakeSession(), "state", {}, FakeServer())
    assert resp["ok"] is True
    # A screen that says nothing is answered "absent", and no number is
    # invented to fill the hole.
    assert resp["state"]["sector"] == {"outcome": "absent"}

    class _AtACommandPrompt(FakeSession):
        def render(self):
            return ["Command [TL=00:00:00]:[4309] (?=Help)? :"]

        def render_text(self, rows=None):
            return "Command [TL=00:00:00]:[4309] (?=Help)? :"

    real = protocol.dispatch(_AtACommandPrompt(), "state", {}, FakeServer())
    assert real["state"]["sector"] == {
        "outcome": "read",
        "sector": 4309,
        "source": "command_prompt",
    }
