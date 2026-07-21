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
from twclient.autopilot import AutopilotEngine
from twclient.control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, ControlLock

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


def test_autopilot_start_threads_credits_stale_ms_into_the_engines_econcaps(fake_daemon, profiles_toml):
    """WO-FA-SAFE (hub-ratified revise, item 3): `credits_stale_ms` is
    threaded through `autopilot_start` exactly like `cash_floor` -- an
    operator arming with an explicit override must get an engine whose
    `EconCaps.credits_stale_ms` actually reflects it, not the 15s
    default `DEFAULT_CREDITS_STALE_MS` would otherwise supply."""
    resp = send_request(
        fake_daemon.sock_path, "autopilot_start", {"profile": "armed", "credits_stale_ms": 42_000}
    )
    assert resp["ok"] is True

    engine = fake_daemon.server.autopilot_engine
    assert engine.caps.credits_stale_ms == 42_000

    send_request(fake_daemon.sock_path, "autopilot_stop")
    _wait_until(lambda: not fake_daemon.server.autopilot_loop.running)


def test_autopilot_start_omitted_credits_stale_ms_keeps_the_default(fake_daemon, profiles_toml):
    """Contrast case: omitting `credits_stale_ms` must NOT force an
    `EconCaps` rebuild with some accidental override -- the engine keeps
    `DEFAULT_CREDITS_STALE_MS` (15s), same as before this revise."""
    from twclient.autopilot import DEFAULT_CREDITS_STALE_MS

    resp = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "armed"})
    assert resp["ok"] is True

    engine = fake_daemon.server.autopilot_engine
    assert engine.caps.credits_stale_ms == DEFAULT_CREDITS_STALE_MS

    send_request(fake_daemon.sock_path, "autopilot_stop")
    _wait_until(lambda: not fake_daemon.server.autopilot_loop.running)


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


class _FakeLoggerForSeed:
    """Minimal stand-in for `logging_util.TranscriptLogger` -- mirrors
    test_world_model_integration.py's own `FakeLogger`, the only surface
    `_log_world_model_failure` actually calls."""

    def __init__(self):
        self.notes = []

    def log_note(self, note):
        self.notes.append(note)


def test_autopilot_snapshot_kwargs_seed_swallows_a_corrupt_sector_file_and_logs(monkeypatch, tmp_path):
    """MED fix (mack re-verify, 2026-07-21): a corrupt on-disk sector
    file makes `plan_find_stardock()` (via `known_graph`/`all_sectors`)
    raise `world_model.WorldModelError` -- a plain `Exception`, NOT an
    `OSError`, so the old `except OSError` around this call let it
    propagate uncaught, crashing the whole tick (both `autopilot_preview`
    and the background `AutopilotLoop`'s `snapshot_provider`) over a pure
    read-availability hiccup. Must swallow-and-log instead (same
    convention as the write-hook immediately above it in this function)
    and return `{}` -- no explore lane this tick, never a crash."""
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path / "world")
    session = FakeAttachSession(initial_screen="Sector  : 1\n\nCommand [TL=00:00:00]:[1] (?=Help)? : ")
    session.auto_login_profile = "default"
    logger = _FakeLoggerForSeed()
    session.logger = logger

    profile = credentials.Profile(name="default", host=session.host, port=1, game_letter="A", handle="Trader1")
    monkeypatch.setattr(credentials, "load_profile", lambda name: profile)

    world_id = world_identity.world_id(session.host, profile.game_letter, profile.handle)
    # A genuinely corrupt sector file -- same truncated-JSON technique
    # test_world_model.py's own corrupt-file tests use.
    path = world_model._sector_path(world_id, 1, state_dir=None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"sector_id": 1,', encoding="utf-8")

    kwargs = protocol._autopilot_snapshot_kwargs(session)

    assert kwargs == {}  # no crash, no explore lane this tick
    assert any("plan_find_stardock" in note for note in logger.notes)


def test_autopilot_snapshot_kwargs_empty_with_no_resolvable_world(fake_daemon):
    assert protocol._autopilot_snapshot_kwargs(fake_daemon.session) == {}


# -- WO-FA1: full chain, state_parser -> cold-start seed -> explore BFS -----
# -- -> a real autonomous live_tick send -------------------------------------


def test_full_chain_real_warps_screen_seeds_world_model_and_drives_a_live_explore_send(
    monkeypatch, tmp_path
):
    """No piece of the WO-FA1 chain is exercised together anywhere else:
    a real (paren-wrapped, 6-destination) "Warps to Sector(s)" screen,
    parsed fresh by `state_parser` (its own dedicated fix), cold-start-
    seeded into the world-model by `_autopilot_snapshot_kwargs` (this is
    the FIRST tick -- nothing was ever previously written for this
    sector), turned into a frontier target by `explore.py`'s BFS, and
    finally sent for real by an autonomous `AutopilotEngine.live_tick()`.
    """
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path / "world")
    screen = (
        "Sector  : 2335\n"
        "Ports   : None\n"
        "Warps to Sector(s) :  (379) - (597) - (1302) - (3424) - (4069) - (4182)\n"
        "Command [TL=00:00:08]:[100] (?=Help)? :"
    )
    session = FakeAttachSession(initial_screen=screen)
    session.auto_login_profile = "armed"

    profile = credentials.Profile(
        name="armed", host=session.host, port=1, game_letter="A", handle="Trader1", autonomous=True
    )
    monkeypatch.setattr(credentials, "load_profile", lambda name: profile)

    kwargs = protocol._autopilot_snapshot_kwargs(session)

    # The cold-start seed must have written all 6 warps under 2335 --
    # never truncated to the first, never dropped.
    world_id = world_identity.world_id(session.host, profile.game_letter, profile.handle)
    assert world_model.get_sector(world_id, 2335)["warps"] == [379, 597, 1302, 3424, 4069, 4182]

    # None of the 6 destinations are mapped yet -- all are depth-1
    # frontier edges from 2335; deterministic (epsilon=0.0) nearest pick
    # is the lowest sector number, 379.
    assert kwargs["explore_next_sector"] == 379
    assert kwargs["explore_mode"] == "hunt"

    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    decision = engine.live_tick(**kwargs)

    assert decision.chosen.kind == "explore"
    assert decision.send_outcome == "sent"
    assert session.sent == [("379", True, False)]


# -- FA9 (pinned, not fixed in this revise): forged in-band sibling block --


@pytest.mark.xfail(
    reason=(
        "FA9: is_genuine_sector_status provenance-hardening not yet built -- "
        "a forged in-band Warps-to-Sector(s) fragment trailing a GENUINE "
        "sector-status block on the SAME screen still wins parse_state()'s "
        "last-match-wins and poisons the cold-start seed under the REAL "
        "current sector; tracked as a multiplayer-arm prerequisite (see "
        "state_parser.is_genuine_sector_status's RESIDUAL note / "
        "protocol._autopilot_snapshot_kwargs's FORGED-BLOCK RESIDUAL note)."
    ),
    strict=False,
)
def test_forged_trailing_sibling_block_must_not_poison_the_seed_or_defeat_the_guard(
    monkeypatch, tmp_path
):
    """Pins cipher's guard-defeat finding (`is_genuine_sector_status()` is a
    SHAPE check, not a provenance check) against the CORRECT (hardened,
    not-yet-built) behavior -- RED today, GREEN once FA9 lands.

    The screen carries a REAL, genuine "Sector : 100" status block
    (warps 12-45-99) followed later on the SAME screen by a WELL-FORMED
    (not merely split-label -- that narrower regex leak is already closed
    above) forged "Warps to Sector(s)" line an in-band chat/broadcast
    fragment could carry. `is_genuine_sector_status()` still returns True
    (the genuine block right after "Sector : 100" satisfies it), and
    `parse_state()`'s deliberate last-match-wins (needed for the real
    stale-scrollback case) currently lets the LATER, forged line win --
    the cold-start seed persists the forged pair under the ship's real
    current sector, `explore.py`'s frontier BFS treats it as a genuine
    depth-1 edge FROM the current sector (`_adjacent_hop_toward`'s
    `current == edge.frm` shortcut hands it back directly -- "safe by
    construction" only when the world-model's belief about the current
    sector's own warps is accurate), and the HIGH backstop guard
    re-parses the SAME buffer and sees the identical forged fragment, so
    it can't catch it either. Once FA9's provenance-hardening lands, the
    genuine warps must win instead."""
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path / "world")
    screen = (
        "Sector  : 100\n"
        "Ports   : None\n"
        "Warps to Sector(s) : 12 - 45 - 99\n"
        "\n"
        "R Someone says: check this out\n"
        "Warps to Sector(s) : 9001 - 9002\n"
        "Command [TL=00:00:08]:[100] (?=Help)? :"
    )
    session = FakeAttachSession(initial_screen=screen)
    session.auto_login_profile = "armed"

    profile = credentials.Profile(
        name="armed", host=session.host, port=1, game_letter="A", handle="Trader1", autonomous=True
    )
    monkeypatch.setattr(credentials, "load_profile", lambda name: profile)

    kwargs = protocol._autopilot_snapshot_kwargs(session)

    world_id = world_identity.world_id(session.host, profile.game_letter, profile.handle)
    sector_rec = world_model.get_sector(world_id, 100)
    assert sector_rec["warps"] == [12, 45, 99], (
        "the seed must persist the GENUINE warps, never a forged trailing in-band fragment"
    )
    assert kwargs.get("explore_next_sector") not in (9001, 9002), (
        "the frontier must never resolve to the forged targets"
    )

    lock = ControlLock()
    engine = AutopilotEngine(session, profile, lock)
    decision = engine.live_tick(**kwargs)
    assert session.sent not in ([("9001", True, False)], [("9002", True, False)]), (
        "must never fire a warp toward a forged in-band target"
    )


# -- Production-composition: socket -> AutopilotLoop -> seed -> send -------


def test_autopilot_start_over_the_real_socket_drives_the_loop_through_the_seed_to_a_live_send(
    fake_daemon, profiles_toml, monkeypatch, tmp_path
):
    """FIX 3 (hub addendum, WO-FA1 final revise): no single existing test
    exercises the EXACT path production use (E2) will run --
    `autopilot_start` dispatched over the REAL unix-domain socket -> a
    background `AutopilotLoop` thread -> `_autopilot_snapshot_kwargs`'s
    cold-start seed -> `explore.py`'s frontier BFS -> a real send through
    `send_and_confirm`. The socket-level tests above use a bare session
    with no resolvable world_id (empty kwargs every tick); the loop tests
    in test_autopilot.py drive a fake `snapshot_provider` directly; the
    full-chain test above calls `_autopilot_snapshot_kwargs()`/
    `live_tick()` directly, bypassing both the socket AND the
    `AutopilotLoop` thread. This is the one test that fires the WHOLE
    production chain end-to-end, in one place."""
    monkeypatch.setattr(world_model, "WORLD_DIR", tmp_path / "world")
    fake_daemon.session._screen = (
        "Sector  : 2335\n"
        "Ports   : None\n"
        "Warps to Sector(s) :  (379) - (597) - (1302) - (3424) - (4069) - (4182)\n"
        "Command [TL=00:00:08]:[100] (?=Help)? :"
    )
    fake_daemon.session.auto_login_profile = "armed"

    resp = send_request(fake_daemon.sock_path, "autopilot_start", {"profile": "armed", "max_ticks": 3})
    assert resp["ok"] is True
    assert resp["running"] is True

    # 3 bounded ticks -- the first fires almost immediately (see
    # AutopilotLoop._run()'s own tick-then-sleep ordering), the loop
    # naturally finishes after ~2 real seconds (2 inter-tick sleeps).
    finished = _wait_until(lambda: not fake_daemon.server.autopilot_loop.running, timeout=8.0)
    assert finished, "the bounded 3-tick loop never finished in time"

    status = send_request(fake_daemon.sock_path, "status")
    assert status["mode"] == MODE_AI_PILOT  # leave_auto_loop() ran in the loop's own finally

    assert fake_daemon.session.sent, "the socket->loop->seed->send chain never fired a single send"
    # Every sent target must be one of the 6 genuine, adjacent warps --
    # never a non-adjacent/garbage number -- proving the nav fix + the
    # HIGH backstop guard both held across every tick, not just the first.
    sent_targets = {int(text) for text, enter, secret in fake_daemon.session.sent}
    assert sent_targets <= {379, 597, 1302, 3424, 4069, 4182}

    # The world-model actually grew (the seed genuinely wrote it, not
    # just a paper trail in the returned kwargs).
    world_id = world_identity.world_id(fake_daemon.session.host, "A", "Trader2")
    sector_rec = world_model.get_sector(world_id, 2335)
    assert sector_rec is not None
    assert sector_rec["warps"] == [379, 597, 1302, 3424, 4069, 4182]
