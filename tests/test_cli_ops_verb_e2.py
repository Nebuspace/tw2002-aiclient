"""WO-P2-OPS-VERB-E2 — ``tw watch`` NDJSON / settle-edge tail over subscribe."""

from __future__ import annotations

import io
import json
from argparse import Namespace
from pathlib import Path

from tw2002_aiclient.session import cli


def test_parser_lists_watch():
    parser = cli.build_parser()
    assert "watch" in parser.format_help()
    args = parser.parse_args(["watch", "--frames", "2", "--json"])
    assert args.func is cli.cmd_watch
    assert args.frames == 2


def test_cmd_watch_daemon_not_running(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.env, "socket_path", lambda run_dir=None: tmp_path / "missing.sock")
    rc = cli.cmd_watch(Namespace(frames=1, json=True, compact=False, run_dir=str(tmp_path)))
    assert rc == 1
    assert "daemon_not_running" in capsys.readouterr().out


def test_cmd_watch_prints_seed_then_stops_at_frames(tmp_path, monkeypatch, capsys):
    """Fake unix peer: one subscribe request → two NDJSON events, then EOF."""
    sock_path = tmp_path / "twd.sock"
    sock_path.write_text("")  # exists check only; connect is mocked

    events = [
        {"ok": True, "screen": ["seed"], "prompt": "seed", "classification": "unknown", "ts": "t0"},
        {
            "ok": True,
            "screen": ["next"],
            "prompt": "next",
            "classification": "unknown",
            "settled_reason": "idle",
            "ts": "t1",
        },
    ]
    payload = b"".join((json.dumps(e) + "\n").encode("utf-8") for e in events)

    class FakeSock:
        def __init__(self):
            self.sent = b""
            self._closed = False

        def connect(self, path):
            assert Path(path) == sock_path

        def sendall(self, data):
            self.sent += data

        def makefile(self, mode):
            assert mode == "rb"
            return io.BytesIO(payload)

        def close(self):
            self._closed = True

    fake = FakeSock()
    monkeypatch.setattr(cli.env, "socket_path", lambda run_dir=None: sock_path)
    monkeypatch.setattr(cli.socket, "socket", lambda *a, **k: fake)

    rc = cli.cmd_watch(
        Namespace(frames=1, json=True, compact=False, run_dir=str(tmp_path))
    )
    assert rc == 0
    assert b'"verb": "subscribe"' in fake.sent or b'"verb":"subscribe"' in fake.sent
    assert fake._closed is True
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert json.loads(out[0])["screen"] == ["seed"]
