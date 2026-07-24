"""Thin proofs for session/protocol.py ``ensure`` dispatch.

Live contract (post WO-P2-025): ``control_lock.acquire_driver`` →
``controller_busy`` (or human/spectate typed refuse) on concurrent ensure;
``already_there`` fast path; no auto-arm; no hud_seed. ``do``/``send`` verbs
still unknown_verb until their WOs land.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import credentials, protocol
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession


class FakeServer:
    """Bare server double — ``control_lock`` optional; unrestricted when
    missing (harness convention matching ``_driving_dispatch``)."""


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


def test_ensure_concurrent_control_lock_returns_controller_busy(profiles_toml):
    server = FakeServer()
    lock = ControlLock()
    lock.acquire_driver()
    server.control_lock = lock
    try:
        resp = protocol.dispatch(
            FakeAttachSession(),
            "ensure",
            {"profile": "default"},
            server,
        )
    finally:
        lock.release_driver()

    assert resp["ok"] is False
    assert resp["error"] == "controller_busy"


def test_ensure_refuses_while_human_attached(profiles_toml):
    server = FakeServer()
    lock = ControlLock()
    lock.take_human()
    server.control_lock = lock
    resp = protocol.dispatch(
        FakeAttachSession(),
        "ensure",
        {"profile": "default"},
        server,
    )
    assert resp["ok"] is False
    assert resp["error"] == "controller_locked_by_human"


def test_ensure_refuses_while_spectate(profiles_toml):
    server = FakeServer()
    lock = ControlLock()
    lock.set_mode("spectate")
    server.control_lock = lock
    resp = protocol.dispatch(
        FakeAttachSession(),
        "ensure",
        {"profile": "default"},
        server,
    )
    assert resp["ok"] is False
    assert resp["error"] == "spectate_read_only"
