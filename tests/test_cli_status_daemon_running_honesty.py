"""WO-MT-03 / SESSION-F7 — ``tw status --json`` must not claim daemon_running
after a failed status round-trip.

``daemon_alive`` only proves a pidfile PID answers ``kill(pid, 0)``. A stale
pidfile or a sock that no longer serves can still make ``cmd_status`` stamp
``daemon_running: True`` while ``ok`` is false — JSON self-contradicts.
"""

from __future__ import annotations

import json
from argparse import Namespace

from tw2002_aiclient.session import cli


def test_status_honest_down_when_daemon_not_alive(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: False)
    rc = cli.cmd_status(Namespace(json=True, compact=False, run_dir=str(tmp_path)))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["daemon_running"] is False
    assert out["ok"] is True
    assert out["connected"] is False


def test_status_does_not_claim_daemon_running_when_round_trip_fails(
    tmp_path, monkeypatch, capsys
):
    """Pidfile looks live; status request fails — must not stamp True."""
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: True)

    def _fail_status(verb, args_payload, *, timeout=15.0, run_dir=None):
        assert verb == "status"
        return {"ok": False, "error": "connect_failed:Connection refused"}

    monkeypatch.setattr(cli, "send_request", _fail_status)
    rc = cli.cmd_status(Namespace(json=True, compact=False, run_dir=str(tmp_path)))
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["daemon_running"] is False
    assert out.get("status_unreachable") is True
    assert "connect_failed" in out.get("error", "")


def test_status_daemon_running_true_only_when_round_trip_ok(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: True)
    monkeypatch.setattr(
        cli,
        "send_request",
        lambda verb, args_payload, *, timeout=15.0, run_dir=None: {
            "ok": True,
            "connected": True,
            "classification": "main_command",
        },
    )
    rc = cli.cmd_status(Namespace(json=True, compact=False, run_dir=str(tmp_path)))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["daemon_running"] is True
    assert "status_unreachable" not in out
