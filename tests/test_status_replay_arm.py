"""WO-STATUS-EXPOSE-REPLAY-ARM — `tw status` exposes the credential-replay arm.

Read-only reporting: `replay_arm` is always present (disarmed ≠ missing key),
tracks `session.auto_login_profile` exactly, and never carries a password.
Live-armed observation is pinned in `test_ensure_from_play.py` (FakeTWGS +
real daemon socket) alongside the existing status Accept.
"""

from __future__ import annotations

import json

from tw2002_aiclient.session.protocol import _status_response

from .conftest import FAKE_HOST, FAKE_PORT, FakeAttachSession


class _BareServer:
    watch_hub = None
    control_lock = None
    autoloop = None


def test_status_reports_disarmed_before_any_mark():
    session = FakeAttachSession()
    session.host = FAKE_HOST
    session.port = FAKE_PORT
    assert session.auto_login_profile is None
    resp = _status_response(session, _BareServer())
    assert "replay_arm" in resp, "absent key must not read as safe"
    arm = resp["replay_arm"]
    assert arm["armed"] is False
    assert arm["profile"] is None
    assert arm["host"] is None
    assert arm["port"] is None


def test_status_reports_armed_from_mark_profile_same_field():
    session = FakeAttachSession()
    session.host = FAKE_HOST
    session.port = FAKE_PORT
    session.mark_profile("scout_example")
    assert session.auto_login_profile == "scout_example"
    resp = _status_response(session, _BareServer())
    arm = resp["replay_arm"]
    assert arm["armed"] is True
    assert arm["profile"] == "scout_example"
    assert arm["profile"] is session.auto_login_profile
    assert arm["host"] == FAKE_HOST
    assert arm["port"] == FAKE_PORT


def test_status_replay_arm_never_includes_password_keys():
    session = FakeAttachSession()
    session.host = FAKE_HOST
    session.port = FAKE_PORT
    session.mark_profile("scout_example")
    resp = _status_response(session, _BareServer())
    blob = json.dumps(resp)
    for forbidden in ("password", "secret", "get_password", "secrets.json"):
        assert forbidden not in blob.lower()
    arm = resp["replay_arm"]
    assert set(arm) == {"armed", "profile", "host", "port"}
