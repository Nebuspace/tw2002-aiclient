"""`tw --run-dir` wiring — default geek socket unchanged; alternate run dirs."""

import json
import sys
from argparse import Namespace
from unittest.mock import patch

import pytest

from twclient import cli

PROJECT_ROOT = cli.PROJECT_ROOT


@pytest.fixture(autouse=True)
def _reset_run_paths():
    cli._configure_run_paths(None)
    yield
    cli._configure_run_paths(None)


def test_resolve_run_dir_default():
    assert cli._resolve_run_dir(None) == PROJECT_ROOT / "run"


def test_resolve_run_dir_relative():
    assert cli._resolve_run_dir("run/ona") == PROJECT_ROOT / "run" / "ona"


def test_paths_for_run_dir():
    run_dir = PROJECT_ROOT / "run" / "ona"
    sock, pid = cli._paths_for_run_dir(run_dir)
    assert sock == run_dir / "twd.sock"
    assert pid == run_dir / "twd.pid"


def test_parser_default_run_dir():
    parser = cli.build_parser()
    args = parser.parse_args(["status"])
    assert args.run_dir is None


def test_parser_run_dir_on_spectate():
    parser = cli.build_parser()
    args = parser.parse_args(["spectate", "--run-dir", "run/ona", "--snapshot"])
    assert args.run_dir == "run/ona"
    assert args.func is cli.cmd_spectate


def test_configure_default_paths():
    cli._configure_run_paths(None)
    assert cli._active_sock_path == PROJECT_ROOT / "run" / "twd.sock"
    assert cli._active_pid_path == PROJECT_ROOT / "run" / "twd.pid"


def test_configure_ona_paths():
    cli._configure_run_paths("run/ona")
    assert cli._active_sock_path == PROJECT_ROOT / "run" / "ona" / "twd.sock"
    assert cli._active_pid_path == PROJECT_ROOT / "run" / "ona" / "twd.pid"


def test_send_request_uses_active_sock(tmp_path):
    run_dir = tmp_path / "custom"
    run_dir.mkdir()
    cli._configure_run_paths(str(run_dir))
    resp = cli.send_request("status", {})
    assert resp == {"ok": False, "error": "daemon_not_running"}


def test_cmd_spectate_passes_configured_paths(monkeypatch, tmp_path):
    run_dir = tmp_path / "run" / "ona"
    run_dir.mkdir(parents=True)
    (run_dir / "twd.sock").touch()
    cli._configure_run_paths(str(run_dir))

    captured = {}

    def fake_snapshot(sock_path, pid_path, frames=1):
        captured["sock"] = sock_path
        captured["pid"] = pid_path
        return 0

    monkeypatch.setattr("twclient.spectate_app.run_snapshot", fake_snapshot)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_spectate(Namespace(snapshot=True, frames=1))
    assert exc.value.code == 0
    assert captured["sock"] == run_dir / "twd.sock"
    assert captured["pid"] == run_dir / "twd.pid"


def test_cmd_watch_connects_configured_sock(monkeypatch, tmp_path):
    run_dir = tmp_path / "run" / "ona"
    run_dir.mkdir(parents=True)
    (run_dir / "twd.sock").touch()
    cli._configure_run_paths(str(run_dir))

    connected = {}

    class FakeSocket:
        def settimeout(self, _):
            pass

        def connect(self, path):
            connected["path"] = path

        def sendall(self, _):
            pass

        def makefile(self, _):
            return self

        def readline(self):
            return b""

        def close(self):
            pass

    monkeypatch.setattr(cli.socket, "socket", lambda *_: FakeSocket())
    cli.cmd_watch(Namespace(frames=0, json=False))
    assert connected["path"] == str(run_dir / "twd.sock")


def test_main_configures_run_dir_from_argv(monkeypatch):
    seen = {}

    def fake_status(args):
        seen["run_dir"] = args.run_dir
        seen["sock"] = cli._active_sock_path

    monkeypatch.setattr(cli, "cmd_status", fake_status)
    monkeypatch.setattr(sys, "argv", ["tw", "status", "--run-dir", "run/ona"])
    cli.main()
    assert seen["run_dir"] == "run/ona"
    assert seen["sock"] == PROJECT_ROOT / "run" / "ona" / "twd.sock"


def test_cmd_status_includes_run_dir_when_daemon_down(capsys):
    """WO-CLI-DEFAULT-PROFILE-HINT: status always reports which run_dir
    this CLI targets so a wrong sock is obvious."""
    cli._configure_run_paths("run/ona")
    with patch.object(cli, "daemon_alive", return_value=False):
        cli.cmd_status(Namespace(json=True))
    out = json.loads(capsys.readouterr().out)
    assert out["daemon_running"] is False
    assert out["run_dir"].endswith("run/ona") or "run/ona" in out["run_dir"].replace("\\", "/")
