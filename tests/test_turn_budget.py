"""WO-AUTOLOOP-TURN-BUDGET — fail-closed remaining-turns floor on AutoLoop.

Mirrors the credit-floor posture (X5): refuse unenforceable budgets at arm,
re-check ``turns_snapshot`` at every player boundary, typed halt codes, and
``cycles`` still refused.
"""

from __future__ import annotations

import threading

import pytest

from tw2002_aiclient.loops import player as player_mod
from tw2002_aiclient.loops.player import (
    HALT_TURN_BUDGET_EXHAUSTED,
    HALT_TURNS_STALE,
    HALT_TURNS_UNKNOWN,
    HALT_TURNS_UNREADABLE,
    TURNS_STALE_MS,
    _check_turn_budget,
    replay_loop,
)
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.session import Session
from tw2002_aiclient.session.state_parser import TurnsSnapshot
from tw2002_aiclient.session import state_parser as sp

from .test_autoloop import ONE_STEP, Server, make_runner, run_to_completion, write_macro
from .test_credits_floor import CreditsWireSession, _screen_with
from .test_loop_player import ANCHOR_158, ONE_STEP as PLAYER_ONE_STEP, NoSendSession, make_loop

STALE_S = TURNS_STALE_MS / 1000.0


class TurnsWireSession(CreditsWireSession):
    """WireSession + real Session turns observe/snapshot (and credits)."""

    observe_turns = Session.observe_turns
    turns_snapshot = Session.turns_snapshot

    def __init__(self, screens, **kwargs):
        super().__init__(screens, **kwargs)
        self.last_turns = None
        self.last_turns_ts = None


def _turns_screen(turns: int) -> str:
    return _screen_with(f"Turns left: {turns}")


def _read(turns, age_s):
    return TurnsSnapshot(outcome=sp.OUTCOME_READ, turns=turns, age_s=age_s)


# --- pure ladder -----------------------------------------------------------


def test_unbudgeted_run_skips_the_check():
    assert _check_turn_budget(None, None, TURNS_STALE_MS) is None
    assert _check_turn_budget(sp.turns_never_observed(), None, TURNS_STALE_MS) is None
    assert _check_turn_budget(("garbage",), None, TURNS_STALE_MS) is None


def test_unobserved_turns_halt_unknown():
    assert (
        _check_turn_budget(sp.turns_never_observed(), 50, TURNS_STALE_MS)
        == HALT_TURNS_UNKNOWN
    )


@pytest.mark.parametrize(
    "answer",
    [
        None,
        (50, 0.0),
        ("timeout", 8.0),
        50,
        {"turns": 50},
    ],
)
def test_non_snapshot_halts_unreadable(answer):
    assert _check_turn_budget(answer, 50, TURNS_STALE_MS) == HALT_TURNS_UNREADABLE


def test_stale_turns_halt():
    assert _check_turn_budget(_read(200, STALE_S), 50, TURNS_STALE_MS) is None
    assert (
        _check_turn_budget(_read(200, STALE_S + 0.001), 50, TURNS_STALE_MS)
        == HALT_TURNS_STALE
    )


def test_budget_exhausted_is_at_or_below():
    assert _check_turn_budget(_read(51, 0.0), 50, TURNS_STALE_MS) is None
    assert (
        _check_turn_budget(_read(50, 0.0), 50, TURNS_STALE_MS)
        == HALT_TURN_BUDGET_EXHAUSTED
    )
    assert (
        _check_turn_budget(_read(0, 0.0), 0, TURNS_STALE_MS)
        == HALT_TURN_BUDGET_EXHAUSTED
    )
    assert _check_turn_budget(_read(1, 0.0), 0, TURNS_STALE_MS) is None


def test_proceed_on_unknown_is_impossible():
    """Mutation pin: unknown must never return None (proceed)."""
    assert _check_turn_budget(sp.turns_never_observed(), 50, TURNS_STALE_MS) is not None


# --- arm / wire ------------------------------------------------------------


def test_args_vocabulary_includes_turn_budget_and_cycles():
    assert autoloop.ARGS_AUTOLOOP_START == frozenset(
        {"name", "floor", "turn_budget", "profit_target", "cycles"}
    )


def test_cycles_accepted_with_turn_budget(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = TurnsWireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    resp = protocol.dispatch(
        session,
        "autoloop_start",
        {"name": "ore-run", "cycles": 2, "turn_budget": 50},
        server,
    )
    assert resp["ok"] is True
    assert resp["run"]["cycles"] == 2
    assert resp["run"]["turn_budget"] == 50
    server.autoloop.stop()


def test_invalid_turn_budget_types_refused(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = TurnsWireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    for bad in (True, 1.5, "50"):
        resp = protocol.dispatch(
            session, "autoloop_start", {"name": "ore-run", "turn_budget": bad}, server
        )
        assert resp == {"ok": False, "error": "invalid_turn_budget"}
    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "turn_budget": -1}, server
    )
    assert resp == {"ok": False, "error": "invalid_turn_budget"}
    assert lock.is_auto_loop_held() is False


def test_turn_budget_unsupported_when_session_cannot_observe(tmp_path):
    """A bare WireSession has no observe_turns / turns_snapshot."""
    from .test_autoloop import WireSession

    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "turn_budget": 50}, server
    )
    assert resp == {"ok": False, "error": "turn_budget_unsupported"}
    assert lock.is_auto_loop_held() is False


def test_budgeted_run_with_no_turns_halts_unknown(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = TurnsWireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "turn_budget": 50}, server
    )
    assert resp["ok"] is True
    assert resp["run"]["turn_budget"] == 50
    run_to_completion(server.autoloop, session)
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "halted"
    assert run["reason"] == HALT_TURNS_UNKNOWN
    assert run["sends_issued"] == 0
    assert session.sent == []


def test_budgeted_run_halts_when_remaining_at_or_below_budget(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = TurnsWireSession([_turns_screen(40), _turns_screen(40)])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "turn_budget": 50}, server
    )
    run_to_completion(server.autoloop, session)
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "halted"
    assert run["reason"] == HALT_TURN_BUDGET_EXHAUSTED
    assert run["sends_issued"] == 0
    assert session.sent == []


def test_budgeted_run_completes_when_remaining_above_budget(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = TurnsWireSession([_turns_screen(200), _turns_screen(199)])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "turn_budget": 50}, server
    )
    assert resp["ok"] is True
    run_to_completion(server.autoloop, session)
    run = protocol.dispatch(session, "autoloop_status", {}, server)["run"]
    assert run["outcome"] == "completed"
    assert run["turn_budget"] == 50
    assert session.turns_snapshot().turns == 199


def test_unbudgeted_run_reports_null_turn_budget(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = TurnsWireSession([ANCHOR_158[0], ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    assert resp["run"]["turn_budget"] is None
    run_to_completion(server.autoloop, session)


def test_replay_loop_refuses_budget_without_turns_port():
    loop = make_loop(PLAYER_ONE_STEP)
    session = NoSendSession(screens=[ANCHOR_158])
    # NoSendSession has no turns() — entry refusal.
    with pytest.raises(TypeError, match="cannot observe turns"):
        replay_loop(loop, session, turn_budget=50)


def test_port_forwards_turns_snapshot_whole(tmp_path):
    session = TurnsWireSession([_turns_screen(123)])
    port = autoloop._ReplayPort(session, ControlLock(), threading.Event())
    assert isinstance(port.turns(), TurnsSnapshot)
    assert port.turns().outcome == sp.OUTCOME_ABSENT
    port.screen()
    snap = port.turns()
    assert isinstance(snap, TurnsSnapshot)
    assert snap.turns == 123
