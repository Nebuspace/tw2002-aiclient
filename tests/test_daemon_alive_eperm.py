"""WO-DAEMON-ALIVE-EPERM — ``daemon_alive`` must not treat EPERM as absent.

``os.kill(pid, 0)`` raising ``PermissionError`` means the process **exists**
but we cannot signal it. Folding that into ``False`` lets ``ensure_raw``
spawn a second daemon (single-connection breach) and lets ``cmd_stop``
claim a success-noop "not running".
"""

from __future__ import annotations

import errno
from argparse import Namespace

import pytest

from tw2002_aiclient.session import cli


def _pidfile(tmp_path, text="12345"):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    pid = run_dir / "twd.pid"
    pid.write_text(text)
    return run_dir, pid


def test_daemon_alive_false_when_pidfile_absent(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setattr(cli.env, "pid_path", lambda run_dir=None: run_dir / "twd.pid")
    assert cli.daemon_alive(run_dir) is False


def test_daemon_alive_true_on_kill_success(tmp_path, monkeypatch):
    run_dir, _ = _pidfile(tmp_path)
    monkeypatch.setattr(cli.env, "pid_path", lambda run_dir=None: run_dir / "twd.pid")
    monkeypatch.setattr(cli.os, "kill", lambda pid, sig: None)
    assert cli.daemon_alive(run_dir) is True


def test_daemon_alive_false_on_esrch(tmp_path, monkeypatch):
    run_dir, _ = _pidfile(tmp_path)
    monkeypatch.setattr(cli.env, "pid_path", lambda run_dir=None: run_dir / "twd.pid")

    def _esrch(pid, sig):
        raise ProcessLookupError(errno.ESRCH, "No such process")

    monkeypatch.setattr(cli.os, "kill", _esrch)
    assert cli.daemon_alive(run_dir) is False


def test_daemon_alive_true_on_eperm(tmp_path, monkeypatch):
    run_dir, _ = _pidfile(tmp_path)
    monkeypatch.setattr(cli.env, "pid_path", lambda run_dir=None: run_dir / "twd.pid")

    def _eperm(pid, sig):
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(cli.os, "kill", _eperm)
    assert cli.daemon_alive(run_dir) is True


def test_daemon_alive_true_on_unreadable_pidfile(tmp_path, monkeypatch):
    run_dir, pid = _pidfile(tmp_path)
    monkeypatch.setattr(cli.env, "pid_path", lambda run_dir=None: run_dir / "twd.pid")

    def _deny_read(*a, **k):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(type(pid), "read_text", _deny_read)
    assert cli.daemon_alive(run_dir) is True


def test_ensure_raw_does_not_spawn_when_eperm_and_sock_present(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sock = run_dir / "twd.sock"
    sock.write_text("")
    (run_dir / "twd.pid").write_text("99")
    (tmp_path / "logs").mkdir()
    spawned = []

    monkeypatch.setattr(cli, "_resolve_profile_connection", lambda name: ("127.0.0.1", 23))
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: True)  # EPERM path
    monkeypatch.setattr(
        cli,
        "send_request",
        lambda verb, args, *, timeout=15.0, run_dir=None: {
            "ok": True,
            "classification": "main_command",
        },
    )
    monkeypatch.setattr(cli.env, "socket_path", lambda run_dir=None: sock)
    monkeypatch.setattr(cli.env, "resolve_run_dir", lambda: run_dir)
    monkeypatch.setattr(cli.env, "LOG_DIR", tmp_path / "logs")

    def _boom(*a, **k):
        spawned.append(True)
        raise AssertionError("must not spawn when daemon_alive")

    monkeypatch.setattr(cli.subprocess, "Popen", _boom)

    resp = cli.ensure_raw("demo", timeout=5.0, run_dir=run_dir)
    assert resp["ok"] is True
    assert spawned == []


def test_cmd_stop_does_not_success_noop_when_eperm(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: True)
    monkeypatch.setattr(
        cli,
        "send_request",
        lambda verb, args, *, timeout=15.0, run_dir=None: {
            "ok": True,
            "stopped": True,
        },
    )
    rc = cli.cmd_stop(Namespace(json=True, compact=False, run_dir=str(tmp_path)))
    assert rc == 0
    out = capsys.readouterr().out
    assert "daemon not running" not in out
    assert '"ok": true' in out.lower() or '"ok":true' in out.replace(" ", "")
