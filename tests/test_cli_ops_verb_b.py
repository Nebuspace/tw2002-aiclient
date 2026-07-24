"""WO-P2-OPS-VERB-B — CLI + protocol for ``tw do`` / ``tw send`` / ``tw read``.

Prove parser wiring, send_request payloads, FakeSession protocol dispatch
(control_lock refuse + case-sensitive wait_prompt), without a live daemon.
"""

from __future__ import annotations

from argparse import Namespace

import pytest

from tw2002_aiclient.session import cli, protocol
from tw2002_aiclient.session.control_lock import ControlLock


class _FakeConn:
    connected = True


class FakeSession:
    def __init__(self, rows, *, settle_reason="idle", settle_elapsed=0.01):
        self._rows = list(rows)
        self.conn = _FakeConn()
        self.last_sent = None
        self.last_sender = None
        self.history = []
        self._history_cap = 50
        self.host = "127.0.0.1"
        self.port = 23
        self.name = "test"
        self._settle_reason = settle_reason
        self._settle_elapsed = settle_elapsed
        self.sent = []

    def render(self):
        return list(self._rows)

    def render_raw(self):
        return list(self._rows)

    def render_text(self, rows=None):
        return "\n".join(rows if rows is not None else self._rows)

    def send(self, text, enter=True, secret=False, sender="app"):
        self.sent.append({"text": text, "enter": enter, "secret": secret, "sender": sender})
        self.last_sent = "<redacted>" if secret else text
        self.last_sender = sender

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        if wait_prompt is not None:
            import re

            re.compile(wait_prompt)  # case-sensitive; raises re.error on bad regex
        return self._settle_reason, self._settle_elapsed

    def record_history(self, verb, args, prompt, classification, settled_reason):
        self.history.append(
            {
                "verb": verb,
                "args": args,
                "prompt": prompt,
                "classification": classification,
                "settled_reason": settled_reason,
            }
        )


class FakeServer:
    def __init__(self, lock=None):
        self.control_lock = lock
        self.stop_called = False

    def request_stop(self):
        self.stop_called = True


_MAIN = ["Command [TL=00:00:00]:[1] (?=Help)? :"]


def test_parser_lists_do_send_read():
    parser = cli.build_parser()
    help_text = parser.format_help()
    for name in ("do", "send", "read"):
        assert name in help_text
    do = parser.parse_args(["do", "T", "--secret", "--wait-prompt", "Command", "--timeout", "2"])
    assert do.func is cli.cmd_do
    assert do.input == "T"
    assert do.secret is True
    assert do.wait_prompt == "Command"
    assert do.enter is True
    send = parser.parse_args(["send", "x", "--no-enter"])
    assert send.func is cli.cmd_send
    assert send.enter is False
    read = parser.parse_args(["read", "--json"])
    assert read.func is cli.cmd_read


def test_cmd_do_forwards_payload(monkeypatch, tmp_path):
    seen = {}

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        seen["verb"] = verb
        seen["args"] = args_payload
        seen["timeout"] = timeout
        seen["run_dir"] = run_dir
        return {"ok": True, "screen": _MAIN, "classification": "main_command"}

    monkeypatch.setattr(cli, "send_request", fake_send)
    args = Namespace(
        input="d",
        enter=True,
        secret=False,
        wait_prompt=None,
        timeout=3.0,
        json=True,
        run_dir=str(tmp_path / "r"),
    )
    assert cli.cmd_do(args) == 0
    assert seen["verb"] == "do"
    assert seen["args"]["input"] == "d"
    assert seen["timeout"] == 8.0  # 3 + 5
    assert seen["run_dir"] == tmp_path / "r"


def test_cmd_send_and_read_forward(monkeypatch):
    calls = []

    def fake_send(verb, args_payload, *, timeout=15.0, run_dir=None):
        calls.append((verb, args_payload, timeout))
        return {"ok": True, "screen": _MAIN}

    monkeypatch.setattr(cli, "send_request", fake_send)
    assert cli.cmd_send(Namespace(input="x", enter=False, secret=True, json=True, run_dir=None)) == 0
    assert cli.cmd_read(Namespace(wait_prompt="Hi", timeout=1.5, json=True, run_dir=None)) == 0
    assert calls[0][0] == "send"
    assert calls[0][1] == {"input": "x", "enter": False, "secret": True}
    assert calls[1][0] == "read"
    assert calls[1][1]["wait_prompt"] == "Hi"
    assert calls[1][2] == 6.5


def test_protocol_do_send_read_fake_session():
    session = FakeSession(_MAIN)
    server = FakeServer()
    do = protocol.dispatch(session, "do", {"input": "d"}, server)
    assert do["ok"] is True
    assert session.sent[0]["sender"] == "app"
    assert session.history[-1]["verb"] == "do"
    assert "settled_reason" in do

    send = protocol.dispatch(session, "send", {"input": "x", "enter": False}, server)
    assert send["ok"] is True
    assert session.sent[-1]["enter"] is False

    read = protocol.dispatch(session, "read", {}, server)
    assert read["ok"] is True
    assert read["settled_reason"] == "idle"


def test_protocol_do_refuses_when_human_holds_lock():
    lock = ControlLock()
    lock.take_human()
    session = FakeSession(_MAIN)
    server = FakeServer(lock)
    resp = protocol.dispatch(session, "do", {"input": "d"}, server)
    assert resp["ok"] is False
    assert "human" in resp["error"]
    assert session.sent == []


def test_protocol_do_bad_wait_prompt_regex():
    session = FakeSession(_MAIN)
    resp = protocol.dispatch(
        session, "do", {"input": "d", "wait_prompt": "("}, FakeServer()
    )
    assert resp["ok"] is False
    assert resp["error"].startswith("bad_wait_prompt_regex:")


def test_protocol_read_case_sensitive_compile_path():
    """wait_prompt compiles without IGNORECASE — bad regex still typed-errors."""
    session = FakeSession(_MAIN)
    # Valid regex that would wrongly match if IGNORECASE were on is not
    # exercised here (FakeSession doesn't re-match); prove the compile path.
    ok = protocol.dispatch(
        session, "read", {"wait_prompt": "Command"}, FakeServer()
    )
    assert ok["ok"] is True
