"""Unit tests for tw2002_aiclient ensure/autopilot adapters (mocked daemon)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import adapters


class _FakeProfile:
    def __init__(self, name="rogue", autopilot=False, host="h", port=23):
        self.name = name
        self.autopilot = autopilot
        self.autonomous = autopilot
        self.host = host
        self.port = port


def test_default_run_dir_for_profile_is_run_slash_name(monkeypatch):
    monkeypatch.setattr(
        "twclient.cli.PROJECT_ROOT", Path("/tmp/twproj"), raising=False,
    )
    # Import path used inside the function:
    import twclient.cli as twcli

    monkeypatch.setattr(twcli, "PROJECT_ROOT", Path("/tmp/twproj"))
    assert adapters.default_run_dir_for_profile("rogue") == Path("/tmp/twproj/run/rogue")


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
