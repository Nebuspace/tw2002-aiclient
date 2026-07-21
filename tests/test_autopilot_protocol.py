"""WO-P1-d protocol/CLI wiring for the §22/§23 autonomous goal-orchestrator
(autopilot.py): `autopilot_preview`/`autopilot_start`/`autopilot_stop`
driven through the real wire protocol against the isolated fake-session
daemon (see conftest.py) -- no curses, no network, never the live game.

Bare `FakeAttachSession` has no `auto_login_profile` set, so
`protocol._autopilot_snapshot_kwargs()` resolves no world_id and returns
`{}` for every test here (the same "bare fake-session test doubles that
predate it" convention `_current_world_id()`'s own docstring documents)
-- these tests prove the WIRING (verb plumbing, the fail-closed gate,
never-sends-on-preview), not the explore/StarDock world-model adapter
itself (see `test_autopilot_snapshot_kwargs_wires_the_explore_lane`
below for that, isolated from the socket).
"""

import time

import pytest

from twclient import credentials, protocol, world_identity, world_model
from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP

from .conftest import FakeAttachSession, send_request


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def profiles_toml(tmp_path, monkeypatch):
    """A non-autonomous ("default") and an autonomous ("armed") profile,
    same table shape test_ensure_protocol.py already establishes."""
    p = tmp_path / "profiles.toml"
    p.write_text(
        "[default]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Trader1"\n'
        "\n"
        "[armed]\n"
        'host = "test.example"\n'
        "port = 2002\n"
        'game_letter = "A"\n'
        'handle = "Trader2"\n'
        "autonomous = true\n"
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", p)
    return p


# -- autopilot_preview ------------------------------------------------------


def test_autopilot_preview_requires_a_profile(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "autopilot_preview", {})
    assert resp == {"ok": False, "error": "missing_profile"}


def test_autopilot_preview_unknown_profile_is_rejected(fake_daemon, profiles_toml):
    resp = send_request(fake_daemon.sock_path, "autopilot_preview", {"profile": "nope"})
    assert resp["ok"] is False
    assert "profile_not_found" in resp["error"]


def test_autopilot_preview_returns_a_decision_and_never_sends(fake_daemon, profiles_toml):
    """Proof-of-life: the real ASSESS -> SELECT pipeline runs against the
    fake daemon's live screen and hands back a decision-trace, for a
    profile whose `autonomous` flag is False -- the dry-run path must
    work regardless."""
    resp = send_request(fake_daemon.sock_path, "autopilot_preview", {"profile": "default"})
    assert resp["ok"] is True
    decision = resp["decision"]
    assert "tick" in decision and "context" in decision and "candidates" in decision and "chosen" in decision
    # No world_id resolvable on this bare fake session -> no known chains/
    # upgrades/frontier -- an honest "nothing to do yet", never a guess.
    assert decision["chosen"] is None
    assert fake_daemon.session.sent == []
    assert fake_daemon.session.raw_sent == []


def test_autopilot_preview_works_even_though_profile_is_not_autonomous(fake_daemon, profiles_toml):
    """The execution-OFF proof: dry-run must succeed with zero regard for
    the gate -- confirmed by never even loading the gate's own error
    path."""
    resp = send_request(fake_daemon.sock_path, "autopilot_preview", {"profile": "default"})
    assert resp["ok"] is True
    profile = credentials.load_profile("default")
    assert profile.autonomous is False


def test_autopilot_preview_populates_the_daemons_reserved_engine_slot(fake_daemon, profiles_toml):
    assert getattr(fake_daemon.server, "autopilot_engine", None) is None
    send_request(fake_daemon.sock_path, "autopilot_preview", {"profile": "default"})
    assert fake_daemon.server.autopilot_engine is not None
    status = send_request(fake_daemon.sock_path, "status")
    assert status["autopilot_trace"] is not None
    assert status["autopilot_trace"]["chosen"] is None


# -- autopilot_start / autopilot_stop ---------------------------------------


def test_autopilot_start_requires_a_profile(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "autopilot_start", {})
    assert resp == {"ok": False, "error": "missing_profile"}


def test_autopilot_start_refuses_when_profile_is_not_autonomous(fake_daemon, profiles_toml):
    """The gate fires: `start` against the non-autonomous "default"
    profile must be refused outright, before a single tick ever runs --
    never a silent no-op that leaves a caller thinking it armed."""
    resp = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "default"})
    assert resp["ok"] is False
    assert "autonomous_disabled" in resp["error"]
    assert fake_daemon.session.sent == []
    assert fake_daemon.session.raw_sent == []
    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == MODE_AI_PILOT
    assert getattr(fake_daemon.server, "autopilot_loop", None) is None


def test_autopilot_start_unknown_profile_is_rejected(fake_daemon, profiles_toml):
    resp = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "nope"})
    assert resp["ok"] is False
    assert "profile_not_found" in resp["error"]


def test_autopilot_start_arms_the_loop_when_autonomous_then_stop_halts_it(fake_daemon, profiles_toml):
    resp = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "armed"})
    assert resp["ok"] is True
    assert resp["running"] is True

    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == MODE_AUTO_LOOP

    stop_resp = send_request(fake_daemon.sock_path, "autopilot_stop")
    assert stop_resp["ok"] is True
    assert stop_resp["stopped"] is True

    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == MODE_AI_PILOT
    assert fake_daemon.server.autopilot_loop.running is False


def test_autopilot_start_refuses_a_second_concurrent_run(fake_daemon, profiles_toml):
    first = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "armed"})
    assert first["ok"] is True

    second = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "armed"})
    assert second == {"ok": False, "error": "already_running"}

    send_request(fake_daemon.sock_path, "autopilot_stop")
    _wait_until(lambda: not fake_daemon.server.autopilot_loop.running)


def test_autopilot_stop_with_nothing_running_is_a_harmless_no_op(fake_daemon):
    resp = send_request(fake_daemon.sock_path, "autopilot_stop")
    assert resp == {"ok": False, "error": "autopilot_not_started"}


def test_autopilot_start_refuses_while_human_attached(fake_daemon, profiles_toml):
    from twclient.interactive_app import AttachInputConn

    conn = AttachInputConn(fake_daemon.sock_path)
    assert conn.connect() is True

    resp = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "armed"})
    assert resp["ok"] is False
    assert resp["error"] == "locked_by_human_attach"

    conn.close()


# -- _autopilot_snapshot_kwargs: the honest explore-only wiring -------------


def test_autopilot_snapshot_kwargs_wires_the_explore_lane(monkeypatch, tmp_path):
    """Isolated from the socket: with a real world_id + a known-graph
    frontier edge seeded on disk, the helper hands back a genuine
    stardock/explore plan -- proving the explore lane is really wired,
    not just documented as wired."""
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path / "world")
    session = FakeAttachSession(initial_screen="Sector  : 1\n\nCommand [TL=00:00:00]:[1] (?=Help)? : ")
    session.auto_login_profile = "default"

    profile = credentials.Profile(name="default", host=session.host, port=1, game_letter="A", handle="Trader1")
    monkeypatch.setattr(credentials, "load_profile", lambda name: profile)

    # `_current_world_id()` keys off session.host (not profile.host) -- see
    # protocol.py's own docstring; derive the exact same slug rather than
    # hand-guessing the sanitized format.
    world_id = world_identity.world_id(session.host, profile.game_letter, profile.handle)
    world_model.upsert_sector(world_id, {"sector_id": 1, "warps": [2]})

    kwargs = protocol._autopilot_snapshot_kwargs(session)
    assert kwargs["explore_next_sector"] == 2
    assert kwargs["explore_mode"] == "hunt"  # StarDock not yet landmarked -- falls back to Map-fill frontier hunt
    assert kwargs["stardock_route"] is None


def test_autopilot_snapshot_kwargs_empty_with_no_resolvable_world(fake_daemon):
    assert protocol._autopilot_snapshot_kwargs(fake_daemon.session) == {}
