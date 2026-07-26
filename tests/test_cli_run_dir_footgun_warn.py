"""WO-CLI-RUN-DIR-FOOTGUN-WARN — config isolation ≠ daemon-socket isolation.

Pin: ``status`` / ``stop`` / ``ensure`` without ``--run-dir`` fail closed when
``TW_CONFIG_DIR`` (or a non-default config dir) is active, and print the
actual run-dir path that *would* have been targeted. Explicit ``--run-dir``
or ``TW_RUN_DIR`` clears the guard. Never touches a live default daemon.
"""

from __future__ import annotations

import json
from argparse import Namespace

from tw2002_aiclient.session import cli, env


def _untouched_daemon_probes(monkeypatch):
    """Any socket/pid touch is a test failure — the guard must refuse first."""

    def boom(*_a, **_k):
        raise AssertionError("guard must refuse before daemon_alive / send_request")

    monkeypatch.setattr(cli, "daemon_alive", boom)
    monkeypatch.setattr(cli, "send_request", boom)
    monkeypatch.setattr(cli, "ensure_raw", boom)


def test_status_fails_closed_when_tw_config_dir_set_without_run_dir(
    monkeypatch, capsys
):
    monkeypatch.setenv("TW_CONFIG_DIR", "/tmp/isolated-config-for-footgun-test")
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    _untouched_daemon_probes(monkeypatch)

    rc = cli.cmd_status(Namespace(json=True, compact=False, run_dir=None))
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["error"] == "run_dir_required_under_config_isolation"
    assert out["run_dir"] == str(env.PROJECT_ROOT / "run")
    assert "Would have targeted run-dir:" in out["detail"]
    assert str(env.PROJECT_ROOT / "run") in out["detail"]


def test_stop_fails_closed_prints_path_on_stderr(monkeypatch, capsys):
    monkeypatch.setenv("TW_CONFIG_DIR", "/tmp/isolated-config-for-footgun-test")
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    _untouched_daemon_probes(monkeypatch)

    rc = cli.cmd_stop(Namespace(json=False, run_dir=None))
    assert rc == 2
    err = capsys.readouterr().err
    assert "ERROR:" in err
    assert str(env.PROJECT_ROOT / "run") in err
    assert "TW_CONFIG_DIR" in err


def test_ensure_fails_closed_under_config_isolation(monkeypatch, capsys):
    monkeypatch.setenv("TW_CONFIG_DIR", "/tmp/isolated-config-for-footgun-test")
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    _untouched_daemon_probes(monkeypatch)

    rc = cli.cmd_ensure(
        Namespace(
            profile="scratch",
            target="main_command",
            timeout=1.0,
            no_auto_arm=False,
            json=True,
            run_dir=None,
        )
    )
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["error"] == "run_dir_required_under_config_isolation"
    assert out["run_dir"] == str(env.PROJECT_ROOT / "run")


def test_explicit_run_dir_clears_footgun_guard(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TW_CONFIG_DIR", "/tmp/isolated-config-for-footgun-test")
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: False)

    alt = tmp_path / "alt-run"
    rc = cli.cmd_status(Namespace(json=True, compact=False, run_dir=str(alt)))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["daemon_running"] is False
    assert out["run_dir"] == str(alt)


def test_tw_run_dir_clears_footgun_guard(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TW_CONFIG_DIR", "/tmp/isolated-config-for-footgun-test")
    alt = tmp_path / "env-run"
    monkeypatch.setenv(env.RUN_DIR_VAR, str(alt))
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: False)
    monkeypatch.setattr(cli.env, "resolve_run_dir", lambda: alt)

    rc = cli.cmd_status(Namespace(json=True, compact=False, run_dir=None))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["run_dir"] == str(alt)


def test_no_isolation_status_still_reaches_daemon_probe(monkeypatch, capsys):
    monkeypatch.delenv("TW_CONFIG_DIR", raising=False)
    monkeypatch.delenv(env.RUN_DIR_VAR, raising=False)
    monkeypatch.setattr(
        cli.credentials, "CONFIG_DIR", env.PROJECT_ROOT / "config"
    )
    monkeypatch.setattr(cli, "daemon_alive", lambda run_dir=None: False)

    rc = cli.cmd_status(Namespace(json=True, compact=False, run_dir=None))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["daemon_running"] is False
    assert out["run_dir"] == str(env.PROJECT_ROOT / "run")
