"""WO-PLAY-HOST-SWITCH-DAEMON — Play-layer retarget on identity mismatch.

Offline pins: ``adapters.ensure_session`` stops the stale daemon once and
retries ``ensure_raw`` under a shared budget. Same-host success never
calls stop. Daemon-side ``_session_identity_mismatch`` stays refuse-only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.session import cli as session_cli


def test_host_mismatch_triggers_stop_then_respawn(monkeypatch, tmp_path: Path):
    calls: list[tuple] = []
    responses = iter(
        [
            {"ok": False, "error": "profile_host_mismatch:beta"},
            {"ok": True, "classification": "main_command"},
        ]
    )

    def fake_ensure_raw(profile, *, target="main_command", timeout=20.0, no_auto_arm=False, run_dir=None):
        calls.append(("ensure_raw", profile, float(timeout)))
        return next(responses)

    def fake_send_request(verb, payload, *, timeout=15.0, run_dir=None):
        calls.append(("wire", verb))
        return {"ok": True, "stopping": True}

    monkeypatch.setattr(session_cli, "ensure_raw", fake_ensure_raw)
    monkeypatch.setattr(session_cli, "send_request", fake_send_request)
    monkeypatch.setattr(session_cli, "daemon_alive", lambda run_dir=None: False)

    result = adapters.ensure_session("beta", run_dir=tmp_path, timeout=20.0)

    assert result.ok is True
    assert result.classification == "main_command"
    assert ("wire", "stop") in calls
    ensure_calls = [c for c in calls if c[0] == "ensure_raw"]
    assert len(ensure_calls) == 2
    assert ensure_calls[0][1] == "beta"
    assert ensure_calls[1][1] == "beta"


def test_port_mismatch_also_retargets(monkeypatch, tmp_path: Path):
    responses = iter(
        [
            {"ok": False, "error": "profile_port_mismatch:gamma"},
            {"ok": True, "class": "main_command"},
        ]
    )
    wires: list[str] = []
    monkeypatch.setattr(
        session_cli,
        "ensure_raw",
        lambda *a, **k: next(responses),
    )
    monkeypatch.setattr(
        session_cli,
        "send_request",
        lambda verb, *a, **k: wires.append(verb) or {"ok": True},
    )
    monkeypatch.setattr(session_cli, "daemon_alive", lambda run_dir=None: False)

    result = adapters.ensure_session("gamma", run_dir=tmp_path, timeout=10.0)
    assert result.ok is True
    assert wires == ["stop"]


def test_same_host_path_never_calls_stop(monkeypatch, tmp_path: Path):
    wires: list[str] = []
    monkeypatch.setattr(
        session_cli,
        "ensure_raw",
        lambda *a, **k: {"ok": True, "classification": "main_command"},
    )
    monkeypatch.setattr(
        session_cli,
        "send_request",
        lambda verb, *a, **k: wires.append(verb) or {"ok": True},
    )

    result = adapters.ensure_session("alpha", run_dir=tmp_path, timeout=20.0)
    assert result.ok is True
    assert wires == []


def test_recovery_capped_at_one_retry(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    def always_mismatch(*a, **k):
        calls.append("ensure_raw")
        return {"ok": False, "error": "profile_host_mismatch:beta"}

    monkeypatch.setattr(session_cli, "ensure_raw", always_mismatch)
    monkeypatch.setattr(
        session_cli,
        "send_request",
        lambda verb, *a, **k: calls.append(f"wire:{verb}") or {"ok": True},
    )
    monkeypatch.setattr(session_cli, "daemon_alive", lambda run_dir=None: False)

    result = adapters.ensure_session("beta", run_dir=tmp_path, timeout=20.0)
    assert result.ok is False
    assert result.reason == adapters.REASON_UNKNOWN
    assert "profile_host_mismatch:beta" in (result.detail or "")
    assert calls.count("ensure_raw") == 2
    assert calls.count("wire:stop") == 1


def test_shared_budget_second_timeout_strictly_smaller(monkeypatch, tmp_path: Path):
    """Freeze monotonic so the stop+poll path burns budget before retry."""
    clock = {"t": 1000.0}
    ensure_timeouts: list[float] = []

    def fake_mono():
        return clock["t"]

    def fake_ensure_raw(profile, *, target="main_command", timeout=20.0, no_auto_arm=False, run_dir=None):
        ensure_timeouts.append(float(timeout))
        if len(ensure_timeouts) == 1:
            clock["t"] += 3.0  # first attempt + stop burn
            return {"ok": False, "error": "profile_host_mismatch:beta"}
        return {"ok": True, "classification": "main_command"}

    monkeypatch.setattr(adapters.time, "monotonic", fake_mono)
    monkeypatch.setattr(adapters.time, "sleep", lambda _s: None)
    monkeypatch.setattr(session_cli, "ensure_raw", fake_ensure_raw)
    monkeypatch.setattr(session_cli, "send_request", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(session_cli, "daemon_alive", lambda run_dir=None: False)

    result = adapters.ensure_session("beta", run_dir=tmp_path, timeout=20.0)
    assert result.ok is True
    assert len(ensure_timeouts) == 2
    assert ensure_timeouts[0] == pytest.approx(20.0)
    assert ensure_timeouts[1] < ensure_timeouts[0]
    assert ensure_timeouts[1] == pytest.approx(17.0)


def test_non_mismatch_failure_does_not_stop(monkeypatch, tmp_path: Path):
    wires: list[str] = []
    monkeypatch.setattr(
        session_cli,
        "ensure_raw",
        lambda *a, **k: {"ok": False, "error": "spawn_failed"},
    )
    monkeypatch.setattr(
        session_cli,
        "send_request",
        lambda verb, *a, **k: wires.append(verb) or {"ok": True},
    )

    result = adapters.ensure_session("beta", run_dir=tmp_path, timeout=20.0)
    assert result.ok is False
    assert result.reason == adapters.REASON_SPAWN_FAILED
    assert wires == []
