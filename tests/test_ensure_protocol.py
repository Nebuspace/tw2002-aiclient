"""Thin proofs for session/protocol.py ``ensure`` dispatch.

Live contract (post-rebirth): ``drive_lock`` → ``controller_busy`` on
concurrent ensure; ``already_there`` fast path; no control_lock / AI_PILOT;
no auto-arm; no hud_seed. Auto-arm / human-attach / MODE_* coverage is
deferred to P2-025 (see also tests/test_ensure_no_auto_arm.py).
"""

from __future__ import annotations

import threading

import pytest

from tw2002_aiclient.session import credentials, protocol

from .conftest import FakeAttachSession


class FakeServer:
    """Bare server double — ``drive_lock`` is optional; ``_dispatch_ensure``
    lazy-creates one when missing."""


@pytest.fixture
def profiles_toml(tmp_path, monkeypatch):
    p = tmp_path / "profiles.toml"
    p.write_text(
        "[default]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Trader1"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", p)
    return p


def test_ensure_already_there_fast_path(profiles_toml):
    """Default FakeAttachSession screen classifies main_command → steps=0."""
    session = FakeAttachSession()
    resp = protocol.dispatch(
        session, "ensure", {"profile": "default"}, FakeServer()
    )
    assert resp["ok"] is True
    assert resp["already_there"] is True
    assert resp["steps"] == 0
    assert session.sent == []
    assert session.auto_login_profile == "default"


def test_ensure_missing_profile():
    resp = protocol.dispatch(FakeAttachSession(), "ensure", {}, FakeServer())
    assert resp == {"ok": False, "error": "missing_profile"}


def test_ensure_profile_not_found(profiles_toml):
    resp = protocol.dispatch(
        FakeAttachSession(),
        "ensure",
        {"profile": "no_such_profile"},
        FakeServer(),
    )
    assert resp["ok"] is False
    assert resp["error"] == "profile_not_found:no_such_profile"


def test_ensure_concurrent_drive_lock_returns_controller_busy(profiles_toml):
    server = FakeServer()
    lock = threading.Lock()
    assert lock.acquire(blocking=False)
    server.drive_lock = lock
    try:
        resp = protocol.dispatch(
            FakeAttachSession(),
            "ensure",
            {"profile": "default"},
            server,
        )
    finally:
        lock.release()

    assert resp["ok"] is False
    assert resp["error"] == "controller_busy"
