"""WO-P2-022 — ensure never surprise-arms App autopilot.

Bare `ensure` and `ensure --no-auto-arm` are identical non-arming paths.
Arming remains a separate, confirm-gated cockpit act (out of scope).
"""

from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.session import cli, credentials, protocol


def test_parser_accepts_no_auto_arm_flag():
    parser = cli.build_parser()
    args = parser.parse_args(["ensure", "--profile", "x", "--no-auto-arm"])
    assert args.no_auto_arm is True
    assert args.func is cli.cmd_ensure


def test_parser_bare_ensure_defaults_no_auto_arm_false():
    """Flag default is False, and `ensure` still never auto-arms (WO-P2-022).

    Precision fix 2026-07-27 (WO-AUDIT-ARM-CLAIM-HONESTY): this used to read
    "runtime still never arms", which is now misleading. The runtime CAN arm
    — `session/autoloop.py`'s `AutoLoopRunner`, reached by the
    `autoloop_start` verb. What remains true is the narrower and actually
    load-bearing claim: `ensure` does not auto-arm as a side effect
    (`protocol.py` keeps `no_auto_arm` accepted-and-unused and leaves
    `_maybe_auto_start_after_ensure` out), so arming stays an explicit,
    separately-requested act.
    """
    parser = cli.build_parser()
    args = parser.parse_args(["ensure", "--profile", "x"])
    assert args.no_auto_arm is False


def test_ensure_raw_forwards_no_auto_arm_on_wire(monkeypatch):
    seen = {}

    def fake_send(verb, args_payload, **kwargs):
        seen["verb"] = verb
        seen["args"] = args_payload
        return {"ok": True, "class": "main_command"}

    monkeypatch.setattr(cli, "daemon_alive", lambda _rd=None: True)
    monkeypatch.setattr(cli, "send_request", fake_send)
    monkeypatch.setattr(
        cli,
        "_resolve_profile_connection",
        lambda _p: ("127.0.0.1", 23),
    )
    # sock must "exist" so we skip spawn
    class _Sock:
        def exists(self):
            return True

    monkeypatch.setattr(cli.env, "socket_path", lambda _rd=None: _Sock())

    bare = cli.ensure_raw("scratch", no_auto_arm=False, timeout=5.0)
    flagged = cli.ensure_raw("scratch", no_auto_arm=True, timeout=5.0)
    assert bare["ok"] and flagged["ok"]
    # Last call was flagged; both shapes are accepted on the wire.
    assert seen["verb"] == "ensure"
    assert seen["args"]["no_auto_arm"] is True
    assert seen["args"]["profile"] == "scratch"


def test_adapters_ensure_session_forwards_no_auto_arm(monkeypatch):
    seen = {}

    def fake_ensure_raw(profile, **kwargs):
        seen["profile"] = profile
        seen.update(kwargs)
        return {"ok": True, "class": "main_command"}

    monkeypatch.setattr(adapters._cli, "ensure_raw", fake_ensure_raw)
    result = adapters.ensure_session("p", no_auto_arm=True, timeout=5.0)
    assert result.ok is True
    assert seen["no_auto_arm"] is True


def test_dispatch_ensure_never_arms_even_when_profile_would(monkeypatch, tmp_path):
    """Bare ensure with autopilot-ish profile metadata still only logs in
    / returns already_there — no autopilot loop start side effect."""
    from tw2002_aiclient.session.control_lock import ControlLock

    session = MagicMock()
    session.conn.connected = True
    session.last_rx = 0.0
    session.render.return_value = ["Command [TL=1000]"]
    # WO-P4-053: build_response()'s bare-rows path (the already_there
    # branch this test exercises) now calls render_with_color() instead
    # of render() -- a bare MagicMock() return value isn't a (rows,
    # color) pair to unpack, so this must be configured explicitly.
    session.render_with_color.return_value = (["Command [TL=1000]"], [])
    session.render_text.return_value = "Command [TL=1000]"
    session.host = "127.0.0.1"
    session.port = 23
    session.name = "twd"

    # Plain object — MagicMock invents a fake control_lock that breaks
    # _control_lock_error's truthiness checks.
    class FakeServer:
        pass

    server = FakeServer()
    server.control_lock = ControlLock()

    # WO-ENSURE-PROFILE-IDENTITY-VERIFY: `ensure` now verifies that the live
    # session is on the server the profile NAMES, resolving the profile
    # through `credentials.resolve_profile_host_port` — an INDEPENDENT store
    # read that the `_load_profile` stub below does not satisfy. This test's
    # subject is auto-arming, not identity, so it supplies a store resolving
    # `armed_profile` to the SAME endpoint its session claims; without it the
    # verb fails closed (`profile_identity_unverified:armed_profile:
    # ProfileNotFound`) and never reaches the arming question at all. Written
    # from `session.host`/`session.port` rather than as a second pair of
    # literals so the two cannot drift apart. This also removes an ambient
    # dependency the stub used to leave open — the resolve otherwise falls
    # through to whatever `config/profiles.toml` the machine happens to have.
    profiles = tmp_path / "profiles.toml"
    profiles.write_text(
        f"[armed_profile]\n"
        f'host = "{session.host}"\n'
        f"port = {session.port}\n"
        'game_letter = "A"\n'
        'handle = "Trader1"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", profiles)

    # Profile loader returns a profile; already-at-target path taken.
    fake_profile = MagicMock()
    fake_profile.name = "armed_profile"
    monkeypatch.setattr(protocol, "_load_profile", lambda _n: (fake_profile, None))
    monkeypatch.setattr(protocol, "classify_screen", lambda *_a, **_k: "main_command")

    resp_bare = protocol.dispatch(session, "ensure", {"profile": "armed_profile", "target": "main_command"}, server)
    resp_flag = protocol.dispatch(
        session,
        "ensure",
        {"profile": "armed_profile", "target": "main_command", "no_auto_arm": True},
        server,
    )
    assert resp_bare.get("ok") is True
    assert resp_flag.get("ok") is True
    # No autopilot arming key / loop start — identical non-arming outcomes.
    assert "autopilot_loop" not in resp_bare
    assert "autopilot_loop" not in resp_flag
    assert resp_bare.get("already_there") is True
    assert resp_flag.get("already_there") is True


def test_status_json_reports_autopilot_not_running(monkeypatch):
    """WO-P2-022 Accept: after ensure, status --json shows App not driving."""
    from tw2002_aiclient.session.control_lock import ControlLock, MODE_APP

    session = MagicMock()
    session.conn.connected = True
    session.last_rx = 0.0
    session.render.return_value = ["Command [TL=1000]"]
    session.render_text.return_value = "Command [TL=1000]"
    session.host = "127.0.0.1"
    session.port = 23
    session.name = "twd"

    class FakeServer:
        pass

    server = FakeServer()
    server.control_lock = ControlLock()
    monkeypatch.setattr(protocol, "classify_screen", lambda *_a, **_k: "main_command")
    resp = protocol.dispatch(session, "status", {}, server)
    assert resp["ok"] is True
    assert resp["autopilot"] == {"running": False}
    assert resp["mode"] == MODE_APP
