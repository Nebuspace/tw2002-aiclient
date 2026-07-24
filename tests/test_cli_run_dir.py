"""WO-P2-021 — CLI / daemon run-dir wiring against the reborn session API.

Proves project-rooted default `run/`, `--run-dir` / `TW_RUN_DIR` overrides,
and pidfile refuse-when-held — without needing a live TWGS.
"""

from __future__ import annotations

import json
import os
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from tw2002_aiclient.session import cli, daemon, env

PROJECT_ROOT = env.PROJECT_ROOT


def test_resolve_run_dir_default():
    assert cli._resolve_run_dir(None) == PROJECT_ROOT / "run"


def test_resolve_run_dir_relative():
    assert cli._resolve_run_dir("run/ona") == PROJECT_ROOT / "run" / "ona"


def test_resolve_run_dir_absolute(tmp_path):
    assert cli._resolve_run_dir(str(tmp_path / "custom")) == tmp_path / "custom"


def test_parser_default_run_dir_none():
    parser = cli.build_parser()
    args = parser.parse_args(["status"])
    assert args.run_dir is None


def test_parser_run_dir_on_status():
    parser = cli.build_parser()
    args = parser.parse_args(["status", "--run-dir", "run/ona"])
    assert args.run_dir == "run/ona"
    assert args.func is cli.cmd_status


def test_parser_run_dir_on_ensure():
    parser = cli.build_parser()
    args = parser.parse_args(["ensure", "--profile", "x", "--run-dir", "/tmp/alt"])
    assert args.run_dir == "/tmp/alt"
    assert args.func is cli.cmd_ensure


def test_send_request_uses_resolved_run_dir(tmp_path):
    run_dir = tmp_path / "custom"
    run_dir.mkdir()
    resp = cli.send_request("status", {}, run_dir=run_dir)
    assert resp == {"ok": False, "error": "daemon_not_running"}


def test_cmd_status_includes_run_dir_when_daemon_down(capsys, tmp_path):
    args = Namespace(json=True, run_dir=str(tmp_path / "run" / "ona"))
    with patch.object(cli, "daemon_alive", return_value=False):
        cli.cmd_status(args)
    out = json.loads(capsys.readouterr().out)
    assert out["daemon_running"] is False
    assert "run/ona" in out["run_dir"].replace("\\", "/")


def test_ensure_raw_propagates_tw_run_dir_to_spawn_env(monkeypatch, tmp_path):
    """Daemon spawn must pass TW_RUN_DIR in the child env (not argv)."""
    run_dir = tmp_path / "alt-run"
    run_dir.mkdir()
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["env"] = kwargs.get("env") or {}
        seen["cwd"] = kwargs.get("cwd")
        raise OSError("stop-after-capture")

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cli, "_resolve_profile_connection", lambda _p: ("127.0.0.1", 23))
    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: False)

    resp = cli.ensure_raw("scratch", timeout=1.0, run_dir=run_dir)
    assert resp["ok"] is False
    assert resp["error"] == "spawn_failed"
    assert seen["env"][env.RUN_DIR_VAR] == str(run_dir)
    assert seen["cwd"] == str(PROJECT_ROOT)


def test_claim_pidfile_refuses_live_holder(tmp_path):
    """WO-P2-021 Accept #3: pidfile guard holds independently per run-dir."""
    pidfile = tmp_path / "twd.pid"
    pidfile.write_text(str(os.getpid()), encoding="utf-8")
    with pytest.raises(daemon._PidfileHeld) as exc:
        daemon._claim_pidfile(pidfile)
    assert exc.value.pid == os.getpid()


def test_claim_pidfile_replaces_stale(tmp_path):
    pidfile = tmp_path / "twd.pid"
    pidfile.write_text("99999999", encoding="utf-8")  # almost-certainly dead
    daemon._claim_pidfile(pidfile)
    assert pidfile.read_text(encoding="utf-8").strip() == str(os.getpid())


def test_default_has_no_per_profile_splinter(monkeypatch):
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    assert cli._resolve_run_dir(None) == PROJECT_ROOT / "run"
    assert "ona" not in str(cli._resolve_run_dir(None))
