"""WO-AUTOLOOP-HAZARD-HALT — game_select + zero-fighters + cycles still refused."""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient.loops.player import (
    HALT_HAZARD_GAME_SELECT,
    HALT_HAZARD_ZERO_FIGHTERS,
    _check_hazard,
    replay_loop,
)
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.state_parser import (
    FightersSnapshot,
    OUTCOME_ABSENT,
    OUTCOME_READ,
    read_fighters_aboard,
)
from tw2002_aiclient.session import state_parser as sp

from .test_autoloop import ONE_STEP, Server, WireSession, make_runner, run_to_completion, write_macro
from .test_credits_floor import _screen_with
from .test_loop_player import ANCHOR_158, ONE_STEP as PLAYER_ONE_STEP, NoSendSession, make_loop
from .test_turn_budget import TurnsWireSession


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class HazardWireSession(TurnsWireSession):
    observe_fighters = Session.observe_fighters
    fighters_snapshot = Session.fighters_snapshot

    def __init__(self, screens, **kwargs):
        super().__init__(screens, **kwargs)
        self.last_fighters = None
        self.last_fighters_ts = None


def test_ship_info_fighters_line_reads_aboard_count():
    text = (FIXTURE_DIR / "ship_info_screen.txt").read_text(encoding="utf-8")
    read = read_fighters_aboard(text)
    assert read.outcome == OUTCOME_READ
    assert read.fighters == 150


def test_encounter_toll_fighters_line_is_not_aboard():
    read = read_fighters_aboard("Fighters: 4 (Somecorp) [Toll]\nOption? (A,D,I,R,P,S,?):?")
    assert read.outcome == OUTCOME_ABSENT


def test_check_hazard_game_select():
    class Obs:
        klass = "game_select"
        fighters = None

    assert _check_hazard(Obs()) == HALT_HAZARD_GAME_SELECT


def test_check_hazard_zero_fighters():
    class Obs:
        klass = "main_command"
        fighters = FightersSnapshot(outcome=OUTCOME_READ, fighters=0, age_s=0.0)

    assert _check_hazard(Obs()) == HALT_HAZARD_ZERO_FIGHTERS


def test_check_hazard_unknown_fighters_do_not_halt():
    class Obs:
        klass = "main_command"
        fighters = sp.fighters_never_observed()

    assert _check_hazard(Obs()) is None


def test_cycles_still_refused(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = HazardWireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "cycles": 10}, server
    )
    assert resp == {"ok": False, "error": "unsupported_arg:cycles"}
    assert "Four of four" in autoloop.__doc__ or "All four rails" in autoloop.__doc__


def test_game_select_halts_before_send(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    gs = (FIXTURE_DIR / "game_select_menu.txt").read_text(encoding="utf-8").rstrip("\n")
    session = HazardWireSession([gs, gs])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    run_to_completion(server.autoloop, session)
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "halted"
    assert run["reason"] == HALT_HAZARD_GAME_SELECT
    assert run["sends_issued"] == 0
    assert session.sent == []


def test_zero_fighters_halts_before_send(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    screen = _screen_with("Fighters       : 0")
    session = HazardWireSession([screen, screen])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    run_to_completion(server.autoloop, session)
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "halted"
    assert run["reason"] == HALT_HAZARD_ZERO_FIGHTERS
    assert run["sends_issued"] == 0
    assert session.sent == []


def test_positive_fighters_do_not_block_completion(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    screen = _screen_with("Fighters       : 150")
    session = HazardWireSession([screen, screen])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    run_to_completion(server.autoloop, session)
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "completed"
    assert session.fighters_snapshot().fighters == 150


def test_replay_loop_without_fighters_port_still_halts_game_select():
    gs = (FIXTURE_DIR / "game_select_menu.txt").read_text(encoding="utf-8").rstrip("\n")
    # NoSendSession has no fighters(); game_select half must still fire.
    prompt = gs.split("\n")[-1].strip()
    session = NoSendSession(screens=[(gs, prompt)])
    result = replay_loop(make_loop(PLAYER_ONE_STEP), session)
    assert result.outcome == "halted"
    assert result.reason == HALT_HAZARD_GAME_SELECT
    assert result.sends_issued == 0
