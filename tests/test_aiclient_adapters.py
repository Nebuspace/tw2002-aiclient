"""Unit tests for tw2002_aiclient ensure/autopilot adapters (mocked daemon)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.screens import _launcher_selectable, _launcher_step


class _FakeProfile:
    def __init__(self, name="rogue", autopilot=False, host="h", port=23):
        self.name = name
        self.autopilot = autopilot
        self.autonomous = autopilot
        self.host = host
        self.port = port


def test_resolve_run_dir_defaults_to_shared_run(monkeypatch):
    import twclient.cli as twcli

    monkeypatch.setattr(twcli, "PROJECT_ROOT", Path("/tmp/twproj"))
    monkeypatch.setattr(twcli, "RUN_DIR", Path("/tmp/twproj/run"))
    monkeypatch.delenv("TW_RUN_DIR", raising=False)
    assert adapters.resolve_run_dir("rogue") == Path("/tmp/twproj/run")


def test_resolve_run_dir_honors_tw_run_dir_env(monkeypatch):
    import twclient.cli as twcli

    monkeypatch.setattr(twcli, "PROJECT_ROOT", Path("/tmp/twproj"))
    monkeypatch.setattr(twcli, "RUN_DIR", Path("/tmp/twproj/run"))
    monkeypatch.setenv("TW_RUN_DIR", "run/rogue")
    assert adapters.resolve_run_dir("anything") == Path("/tmp/twproj/run/rogue")


def test_resolve_run_dir_explicit_wins_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TW_RUN_DIR", "run/rogue")
    assert adapters.resolve_run_dir("x", run_dir=tmp_path / "custom") == tmp_path / "custom"


def test_default_run_dir_for_profile_aliases_resolve(monkeypatch):
    import twclient.cli as twcli

    monkeypatch.setattr(twcli, "PROJECT_ROOT", Path("/tmp/twproj"))
    monkeypatch.setattr(twcli, "RUN_DIR", Path("/tmp/twproj/run"))
    monkeypatch.delenv("TW_RUN_DIR", raising=False)
    assert adapters.default_run_dir_for_profile("rogue") == Path("/tmp/twproj/run")


def test_ensure_and_sync_autopilot_off_stops_trainer(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda name, run_dir=None, timeout=60.0: (
            calls.append(("ensure", name, str(run_dir))) or {"ok": True, "classification": "main_command"}
        ),
    )
    monkeypatch.setattr(
        adapters.credentials, "load_profile",
        lambda name, **k: _FakeProfile(name=name, autopilot=False),
    )
    monkeypatch.setattr(
        adapters, "stop_autopilot",
        lambda run_dir=None, profile_name=None: (
            calls.append(("stop", str(run_dir))) or {"ok": True}
        ),
    )
    monkeypatch.setattr(
        adapters, "arm_autopilot",
        lambda name, run_dir=None, **k: (_ for _ in ()).throw(AssertionError("must not arm")),
    )

    out = adapters.ensure_and_sync_autopilot("rogue", run_dir=tmp_path / "rogue")
    assert out["ok"] is True
    assert out["phase"] == "manual"
    assert ("ensure", "rogue", str(tmp_path / "rogue")) in calls
    assert any(c[0] == "stop" for c in calls)


def test_ensure_and_sync_autopilot_on_arms_trainer(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda name, run_dir=None, timeout=60.0: {"ok": True},
    )
    monkeypatch.setattr(
        adapters.credentials, "load_profile",
        lambda name, **k: _FakeProfile(name=name, autopilot=True),
    )
    monkeypatch.setattr(
        adapters, "arm_autopilot",
        lambda name, run_dir=None, **k: (
            calls.append(("arm", name, str(run_dir))) or {"ok": True}
        ),
    )
    monkeypatch.setattr(
        adapters, "stop_autopilot",
        lambda **k: (_ for _ in ()).throw(AssertionError("must not stop")),
    )

    out = adapters.ensure_and_sync_autopilot("rogue", run_dir=tmp_path / "rogue")
    assert out["ok"] is True
    assert out["phase"] == "armed"
    assert calls == [("arm", "rogue", str(tmp_path / "rogue"))]


def test_ensure_and_sync_propagates_ensure_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda *a, **k: {"ok": False, "error": "daemon_down"},
    )
    out = adapters.ensure_and_sync_autopilot("rogue", run_dir=tmp_path / "rogue")
    assert out["ok"] is False
    assert out["phase"] == "ensure"
    assert "daemon_down" in out["message"]


def test_toggle_autopilot_and_sync_on(monkeypatch, tmp_path):
    state = {"ap": False}

    def _load(name, **k):
        return _FakeProfile(name=name, autopilot=state["ap"])

    def _set(name, enabled, profiles_path=None):
        state["ap"] = bool(enabled)

    calls = []
    monkeypatch.setattr(adapters.credentials, "load_profile", _load)
    monkeypatch.setattr(adapters, "set_autopilot", _set)
    monkeypatch.setattr(
        adapters, "arm_autopilot",
        lambda name, run_dir=None, **k: (
            calls.append("arm") or {"ok": True}
        ),
    )
    monkeypatch.setattr(
        adapters, "stop_autopilot",
        lambda **k: (calls.append("stop") or {"ok": True}),
    )

    out = adapters.toggle_autopilot_and_sync("rogue", run_dir=tmp_path / "rogue")
    assert out["ok"] is True
    assert out["autopilot"] is True
    assert state["ap"] is True
    assert calls == ["arm"]


def _write_launcher_profiles(tmp_path, body: str) -> Path:
    p = tmp_path / "profiles.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_list_launcher_rows_active_first_and_marks_retired(tmp_path):
    servers = tmp_path / "servers.toml"
    servers.write_text(
        '[servers.demo]\nhostname = "demo.example"\nport = 2002\n'
        'transport = "telnet"\nfront_end = "direct"\nstatus = "listed"\n',
        encoding="utf-8",
    )
    p = _write_launcher_profiles(
        tmp_path,
        '[zeta]\nserver = "demo"\ngame_letter = "Z"\nhandle = "Zeta"\n'
        'retired = true\n'
        '[alpha]\nserver = "demo"\ngame_letter = "A"\nhandle = "Alpha"\n'
        'autopilot = true\n'
        '[beta]\nserver = "demo"\ngame_letter = "B"\nhandle = "Beta"\n'
        'retired = true\n',
    )
    rows = adapters.list_launcher_rows(profiles_path=p, servers_path=servers)
    assert [r["name"] for r in rows] == ["alpha", "beta", "zeta"]
    assert rows[0]["retired"] is False
    assert rows[0]["autopilot"] is True
    assert rows[1]["retired"] is True
    assert rows[2]["retired"] is True


def test_list_launcher_rows_omitted_retired_is_active(tmp_path):
    servers = tmp_path / "servers.toml"
    servers.write_text(
        '[servers.demo]\nhostname = "demo.example"\nport = 2002\n'
        'transport = "telnet"\nfront_end = "direct"\nstatus = "listed"\n',
        encoding="utf-8",
    )
    p = _write_launcher_profiles(
        tmp_path,
        '[live]\nserver = "demo"\ngame_letter = "L"\nhandle = "Live"\n',
    )
    rows = adapters.list_launcher_rows(profiles_path=p, servers_path=servers)
    assert len(rows) == 1
    assert rows[0]["retired"] is False


def test_launcher_selectable_skips_retired():
    rows = [
        {"name": "a", "retired": False},
        {"name": "b", "retired": True},
        {"name": "c", "retired": False},
    ]
    # Create index = 3
    assert _launcher_selectable(rows) == [0, 2, 3]


def test_launcher_step_skips_retired_rows():
    rows = [
        {"name": "a", "retired": False},
        {"name": "b", "retired": True},
        {"name": "c", "retired": False},
    ]
    # From active a (0) down → c (2), skipping retired b
    assert _launcher_step(0, rows, 1) == 2
    # From c down → Create (3)
    assert _launcher_step(2, rows, 1) == 3
    # From Create up → c
    assert _launcher_step(3, rows, -1) == 2
    # From a up → Create (wrap)
    assert _launcher_step(0, rows, -1) == 3


def test_run_attach_delegates_to_interactive_app(monkeypatch, tmp_path):
    """Thin wrap: configure run_dir, hand sock/pid to interactive_app."""
    import twclient.cli as twcli
    import twclient.interactive_app as interactive_app

    sock = tmp_path / "twd.sock"
    pid = tmp_path / "twd.pid"
    sock.write_text("", encoding="utf-8")
    pid.write_text("1\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        adapters, "_configure",
        lambda rd: calls.append(("cfg", str(rd))),
    )
    monkeypatch.setattr(twcli, "_active_sock_path", sock)
    monkeypatch.setattr(twcli, "_active_pid_path", pid)
    monkeypatch.setattr(
        interactive_app,
        "run_interactive_attach",
        lambda s, p: calls.append(("attach", Path(s), Path(p))) or 0,
    )

    out = adapters.run_attach("rogue", run_dir=tmp_path)
    assert out["ok"] is True
    assert out["code"] == 0
    assert ("cfg", str(tmp_path)) in calls
    assert ("attach", sock, pid) in calls


def test_run_attach_reports_daemon_not_running(monkeypatch, tmp_path):
    import twclient.cli as twcli

    missing = tmp_path / "nope.sock"
    monkeypatch.setattr(adapters, "_configure", lambda rd: None)
    monkeypatch.setattr(twcli, "_active_sock_path", missing)

    out = adapters.run_attach("rogue", run_dir=tmp_path)
    assert out["ok"] is False
    assert out["error"] == "daemon_not_running"


def test_suspend_and_attach_restores_curses(monkeypatch, tmp_path):
    """Play-screen suspend idiom: endwin → attach → reset, never raise."""
    import curses

    calls = []
    monkeypatch.setattr(curses, "def_prog_mode", lambda: calls.append("def_prog_mode"))
    monkeypatch.setattr(curses, "endwin", lambda: calls.append("endwin"))
    monkeypatch.setattr(curses, "reset_prog_mode", lambda: calls.append("reset_prog_mode"))
    monkeypatch.setattr(
        adapters,
        "run_attach",
        lambda name=None, run_dir=None: (
            calls.append(("run_attach", name, str(run_dir))) or {"ok": True, "code": 0}
        ),
    )

    class _FakeStdscr:
        def clear(self):
            calls.append("clear")

        def refresh(self):
            calls.append("refresh")

    err = adapters.suspend_and_attach(_FakeStdscr(), "rogue", run_dir=tmp_path)
    assert err is None
    assert calls == [
        "def_prog_mode",
        "endwin",
        ("run_attach", "rogue", str(tmp_path)),
        "reset_prog_mode",
        "clear",
        "refresh",
    ]


def test_suspend_and_attach_surfaces_failure_and_still_restores(monkeypatch, tmp_path):
    import curses

    calls = []
    monkeypatch.setattr(curses, "def_prog_mode", lambda: None)
    monkeypatch.setattr(curses, "endwin", lambda: None)
    monkeypatch.setattr(curses, "reset_prog_mode", lambda: calls.append("reset_prog_mode"))
    monkeypatch.setattr(
        adapters,
        "run_attach",
        lambda name=None, run_dir=None: {"ok": False, "error": "locked_by_auto_loop"},
    )

    class _FakeStdscr:
        def clear(self):
            calls.append("clear")

        def refresh(self):
            calls.append("refresh")

    err = adapters.suspend_and_attach(_FakeStdscr(), "rogue", run_dir=tmp_path)
    assert err == "locked_by_auto_loop"
    assert calls == ["reset_prog_mode", "clear", "refresh"]