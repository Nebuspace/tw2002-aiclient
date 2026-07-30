"""WO-AUTOLOOP-CYCLES — unlock N passes under 4/4 rails; hard ceiling clamp."""

from __future__ import annotations

import pytest

from tw2002_aiclient.loops.player import OUTCOME_COMPLETED, OUTCOME_HALTED
from tw2002_aiclient.rule_engine import SCOPE_ONE_SHOT, SCOPE_REPEATING, Rule, select_rule
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session.control_lock import ControlLock

from .test_autoloop import (
    ANCHOR_158,
    ONE_STEP,
    Server,
    WireSession,
    make_runner,
    run_to_completion,
    write_macro,
)
from .test_loop_player import ODD


def test_hard_ceiling_constant_is_fifty():
    assert autoloop.CYCLES_HARD_CEILING == 50
    assert "cycles" in autoloop.ARGS_AUTOLOOP_START


def test_valid_cycles_runs_that_many_passes(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    # Stay on main_command forever: ONE_STEP expects that post-class.
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "cycles": 3}, server
    )
    assert resp["ok"] is True
    assert resp["run"]["cycles"] == 3
    snap = run_to_completion(runner, session)
    assert snap.report.outcome == OUTCOME_COMPLETED
    assert snap.report.cycles == 3
    assert snap.report.sends_issued == 3
    assert [t for t, *_ in session.sent] == ["P", "P", "P"]


def test_over_ceiling_clamps(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    resp = protocol.dispatch(
        session,
        "autoloop_start",
        {"name": "ore-run", "cycles": autoloop.CYCLES_HARD_CEILING + 10},
        server,
    )
    assert resp["ok"] is True
    assert resp["run"]["cycles"] == autoloop.CYCLES_HARD_CEILING
    # Do not run 50 passes in the suite — stop immediately so we only pin clamp.
    runner.stop()
    snap = runner.snapshot()
    assert snap.report.cycles == autoloop.CYCLES_HARD_CEILING


@pytest.mark.parametrize("bad", [True, False, 0, -1, 1.5, "3"])
def test_invalid_cycles_refused(tmp_path, bad):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "cycles": bad}, server
    )
    assert resp == {"ok": False, "error": "invalid_cycles"}
    assert lock.is_auto_loop_held() is False
    assert session.sent == []


def test_bool_cycles_refused_at_runner(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    runner = make_runner(tmp_path, session, ControlLock())
    with pytest.raises(autoloop.AutoLoopRefused) as exc:
        runner.start("ore-run", cycles=True)
    assert str(exc.value) == "invalid_cycles"


def test_early_halt_stops_further_passes(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    # Pass 1 completes on main_command; pass 2 post-class sees ODD → halt;
    # passes 3–5 must not run.
    screens = [ANCHOR_158[0], ANCHOR_158[0], ODD[0]]
    session = WireSession(screens)
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "cycles": 5}, server
    )
    assert resp["ok"] is True
    snap = run_to_completion(runner, session)
    assert snap.report.outcome == OUTCOME_HALTED
    assert snap.report.sends_issued == 2
    assert [t for t, *_ in session.sent] == ["P", "P"]


def test_omitted_cycles_is_one_pass(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    runner = make_runner(tmp_path, session, lock)
    server = Server(session, lock, runner)

    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    assert resp["ok"] is True
    assert resp["run"]["cycles"] == 1
    snap = run_to_completion(runner, session)
    assert snap.report.outcome == OUTCOME_COMPLETED
    assert snap.report.sends_issued == 1


def test_force_and_param_still_refused(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([ANCHOR_158[0]])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))
    for arg in ("force", "param"):
        resp = protocol.dispatch(
            session, "autoloop_start", {"name": "ore-run", arg: 1}, server
        )
        assert resp == {"ok": False, "error": f"unsupported_arg:{arg}"}


def test_docstring_says_cycles_accepted_under_rails():
    doc = autoloop.__doc__ or ""
    assert "All four rails are built" in doc
    assert "accepted" in doc.lower()
    assert "CYCLES_HARD_CEILING" in doc or "clamp" in doc.lower()


def test_decision_carries_winning_scope():
    rules = [
        Rule(
            rule_id="r1",
            screen_match="main_command",
            do="ore-run",
            priority=1,
            scope=SCOPE_REPEATING,
            approved=True,
        )
    ]
    d = select_rule("main_command", rules, {})
    assert d.fired
    assert d.scope == SCOPE_REPEATING

    rules[0] = Rule(
        rule_id="r1",
        screen_match="main_command",
        do="ore-run",
        priority=1,
        scope=SCOPE_ONE_SHOT,
        approved=True,
    )
    d2 = select_rule("main_command", rules, {})
    assert d2.scope == SCOPE_ONE_SHOT
