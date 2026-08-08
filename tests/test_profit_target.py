"""WO-BUILD-PROFIT-TARGET-HALT -- an ADDITIONAL stop that halts once profit
(credits delta from this daemon session's first strict balance) reaches or
exceeds a target, mirroring the credit floor's exact fail-closed shape with
the direction inverted.

This is a companion slice, not a re-derivation: the freshness gate, the
truthy-tuple hazard, the entry-refusal-before-first-observation contract, and
the per-boundary re-check are already proven exhaustively (including the
injected-cheat mutation pass) for the floor in ``test_credits_floor.py`` and
for the turn budget in ``test_turn_budget.py``. Profit shares the exact same
``_validate_snapshot``-shaped machinery (``ProfitSnapshot`` is built from the
same helper as ``CreditsSnapshot``) and the exact same ``replay_loop``
boundary-ladder placement, so this file proves the profit-specific surface
--  the pure ``_check_profit_target`` ladder, wiring into a real replay, and
the AutoLoop/TradeChain arm-time refusals -- without re-litigating freshness
math or truthy-tuple handling a second time.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import stopbanner
from tw2002_aiclient.loops import player as player_mod
from tw2002_aiclient.loops.player import (
    CREDITS_STALE_MS,
    HALT_CREDITS_UNKNOWN,
    HALT_FLOOR_REACHED,
    HALT_PROFIT_STALE,
    HALT_PROFIT_TARGET_REACHED,
    HALT_PROFIT_UNKNOWN,
    HALT_PROFIT_UNREADABLE,
    HALT_REASONS,
    OUTCOME_COMPLETED,
    OUTCOME_HALTED,
    _check_profit_target,
    replay_loop,
)
from tw2002_aiclient.session import autoloop, protocol
from tw2002_aiclient.session import state_parser as sp
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.hud_tracking import ProfitSnapshot, profit_never_observed
from tw2002_aiclient.session.session import Session

from .test_autoloop import (
    ONE_STEP,
    Server,
    WireSession,
    make_runner,
    run_to_completion,
    write_macro,
)
from .test_loop_player import ANCHOR_158, ScriptedSession, make_loop

STALE_S = CREDITS_STALE_MS / 1000.0

ONE_STEP_LOOP = make_loop([("P", None, "main_command")])
TWO_STEP_LOOP = make_loop(
    [("P", None, "main_command"), ("Q", None, "main_command")]
)
CLEAN_SCREENS = [ANCHOR_158, ANCHOR_158, ANCHOR_158]


def _read(profit, age_s):
    return ProfitSnapshot(outcome=sp.OUTCOME_READ, profit=profit, age_s=age_s)


# ==========================================================================
# 1 -- the decision, branch by branch (pure, mirrors _check_floor's ladder)
# ==========================================================================


def test_an_untargeted_run_has_nothing_to_check():
    """`profit_target=None` returns immediately regardless of the reading --
    including a profit that would otherwise halt."""
    assert _check_profit_target(None, None, CREDITS_STALE_MS) is None
    assert _check_profit_target(profit_never_observed(), None, CREDITS_STALE_MS) is None
    assert _check_profit_target(("garbage",), None, CREDITS_STALE_MS) is None
    assert _check_profit_target(_read(10_000, 0.0), None, CREDITS_STALE_MS) is None


def test_an_unobserved_profit_halts_profit_unknown():
    assert (
        _check_profit_target(profit_never_observed(), 1000, CREDITS_STALE_MS)
        == HALT_PROFIT_UNKNOWN
    )


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(None, id="port-returned-None"),
        pytest.param((500, 0.0), id="raw-value-ts-pair"),
        pytest.param(("timeout", 8.0), id="settle-2-tuple"),
        pytest.param(500, id="bare-int"),
        pytest.param({"profit": 500, "age_s": 0.0}, id="dict"),
        pytest.param(sp.CreditsSnapshot(outcome=sp.OUTCOME_READ, balance=500, age_s=0.0),
                     id="wrong-snapshot-type"),
    ],
)
def test_anything_that_is_not_a_profit_snapshot_halts_rather_than_being_interpreted(answer):
    """The same truthy-tuple hazard the floor guards against: every value
    above is truthy (or a plausible-looking snapshot of the WRONG type), and
    a loose check would read one of them as a healthy profit and press on."""
    assert _check_profit_target(answer, 1000, CREDITS_STALE_MS) == HALT_PROFIT_UNREADABLE


def test_the_freshness_window_is_a_real_boundary():
    assert _check_profit_target(_read(200, STALE_S), 1000, CREDITS_STALE_MS) is None
    assert (
        _check_profit_target(_read(200, STALE_S - 0.001), 1000, CREDITS_STALE_MS)
        is None
    )
    assert (
        _check_profit_target(_read(200, STALE_S + 0.001), 1000, CREDITS_STALE_MS)
        == HALT_PROFIT_STALE
    )
    # Stale halts even when comfortably above target -- a stale-but-healthy
    # reading must never mask a real target crossing that happened since.
    assert (
        _check_profit_target(_read(1_000_000, STALE_S * 4), 1000, CREDITS_STALE_MS)
        == HALT_PROFIT_STALE
    )


def test_the_target_comparison_is_at_or_above():
    """Inverted direction from the floor's `<=`: a target of 1000 means
    "stop once profit reaches 1000", not "stop once it exceeds 1000"."""
    assert _check_profit_target(_read(999, 0.0), 1000, CREDITS_STALE_MS) is None
    assert (
        _check_profit_target(_read(1000, 0.0), 1000, CREDITS_STALE_MS)
        == HALT_PROFIT_TARGET_REACHED
    )
    assert (
        _check_profit_target(_read(1001, 0.0), 1000, CREDITS_STALE_MS)
        == HALT_PROFIT_TARGET_REACHED
    )
    # A target of 0 (any non-negative profit) fires immediately.
    assert (
        _check_profit_target(_read(0, 0.0), 0, CREDITS_STALE_MS)
        == HALT_PROFIT_TARGET_REACHED
    )
    # Negative profit (a run currently underwater) never reaches a
    # non-negative target and never halts on this rail.
    assert _check_profit_target(_read(-500, 0.0), 1000, CREDITS_STALE_MS) is None


def test_every_new_halt_code_is_in_the_closed_vocabulary():
    for code in (
        HALT_PROFIT_TARGET_REACHED,
        HALT_PROFIT_UNKNOWN,
        HALT_PROFIT_STALE,
        HALT_PROFIT_UNREADABLE,
    ):
        assert code in HALT_REASONS


def test_every_new_code_has_a_human_label():
    labels = stopbanner.INTERVENTION_REASON_LABELS
    for code in (
        HALT_PROFIT_TARGET_REACHED,
        HALT_PROFIT_UNKNOWN,
        HALT_PROFIT_STALE,
        HALT_PROFIT_UNREADABLE,
    ):
        assert code in labels
        status = {"intervention": {"needs_attention": True, "reasons": [{"code": code}]}}
        banner = "\n".join(
            stopbanner.compose_stop_banner_lines(status, width=120, height=3)
        )
        assert labels[code] in banner, banner
        assert code not in banner, banner  # human label, not the RAW identifier


# ==========================================================================
# 2 -- enforcement inside a real replay
# ==========================================================================


class ProfitScript:
    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = 0

    def next(self):
        self.asked += 1
        return self.answers.pop(0) if self.answers else None


class TargetedSession(ScriptedSession):
    """X3's scripted port plus a `profit()`, mirroring `FlooredSession`."""

    def __init__(self, screens, profits, **kwargs):
        super().__init__(screens, **kwargs)
        self._profit = ProfitScript(profits)

    def profit(self):
        self.calls.append("profit")
        return self._profit.next()


class TargetedNoSendSession(TargetedSession):
    def send_and_confirm(self, keystrokes, wait_prompt):  # pragma: no cover
        raise AssertionError(
            f"the player sent {keystrokes!r} past its own profit target -- a stop "
            "that sends first and reports afterwards is not a stop"
        )


class SendsOnceTargetedSession(TargetedSession):
    def send_and_confirm(self, keystrokes, wait_prompt):
        if self.sends:  # pragma: no cover - must not run
            raise AssertionError(
                f"the player sent {keystrokes!r} after profit crossed the target"
            )
        return super().send_and_confirm(keystrokes, wait_prompt)


UNDER_TARGET = _read(200, 0.0)
AT_TARGET = _read(1000, 0.0)
STALE = _read(1000, STALE_S * 3)
UNOBSERVED = profit_never_observed()


def test_a_run_with_no_target_never_asks_for_profit():
    session = TargetedSession(CLEAN_SCREENS, [])
    result = replay_loop(ONE_STEP_LOOP, session)
    assert result.outcome == OUTCOME_COMPLETED
    assert session._profit.asked == 0
    assert "profit" not in session.calls


def test_the_same_scenario_completes_when_profit_stays_under_target():
    """THE POSITIVE CONTROL -- every halt below runs on these exact fixtures
    with only the profit reading changed."""
    session = TargetedSession(CLEAN_SCREENS, [UNDER_TARGET, UNDER_TARGET])
    result = replay_loop(ONE_STEP_LOOP, session, profit_target=1000)
    assert result.outcome == OUTCOME_COMPLETED
    assert result.reason is None
    assert session.sends == [("P", None)]
    assert session._profit.asked == 2  # boundary 0 and boundary 1


@pytest.mark.parametrize(
    "answer,expected",
    [
        pytest.param(UNOBSERVED, HALT_PROFIT_UNKNOWN, id="never-observed"),
        pytest.param(STALE, HALT_PROFIT_STALE, id="too-old"),
        pytest.param(AT_TARGET, HALT_PROFIT_TARGET_REACHED, id="at-or-above-target"),
        pytest.param((1000, 0.0), HALT_PROFIT_UNREADABLE, id="raw-tuple"),
        pytest.param(None, HALT_PROFIT_UNREADABLE, id="nothing"),
    ],
)
def test_boundary_zero_halts_before_a_single_byte(answer, expected):
    session = TargetedNoSendSession(CLEAN_SCREENS, [answer])
    result = replay_loop(ONE_STEP_LOOP, session, profit_target=1000)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason == expected
    assert result.halted_at == player_mod.BEFORE_FIRST_SEND
    assert result.sends_issued == 0
    assert session.sends == []


@pytest.mark.parametrize(
    "answer,expected",
    [
        pytest.param(UNOBSERVED, HALT_PROFIT_UNKNOWN, id="never-observed"),
        pytest.param(STALE, HALT_PROFIT_STALE, id="too-old"),
        pytest.param(AT_TARGET, HALT_PROFIT_TARGET_REACHED, id="at-or-above-target"),
    ],
)
def test_the_target_is_re_checked_before_every_send_not_only_at_launch(answer, expected):
    session = SendsOnceTargetedSession(CLEAN_SCREENS, [UNDER_TARGET, answer])
    result = replay_loop(TWO_STEP_LOOP, session, profit_target=1000)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason == expected
    assert result.halted_at == 0  # halted AT step 0's boundary; step 1 never sent
    assert result.sends_issued == 1
    assert session.sends == [("P", None)]


def test_the_final_boundary_is_checked_too():
    session = TargetedSession(CLEAN_SCREENS, [UNDER_TARGET, AT_TARGET])
    result = replay_loop(ONE_STEP_LOOP, session, profit_target=1000)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason == HALT_PROFIT_TARGET_REACHED


def test_a_more_sovereign_guard_outranks_the_target_and_the_target_still_bites():
    """The floor sits between the gate/hazard rungs and the target -- both
    are re-checked every boundary, so a healthy target-armed run still halts
    on a higher-priority guard when one fires, and the target rail itself
    still bites once that guard clears."""
    from .test_loop_player import MONEY

    session = TargetedSession([MONEY], [AT_TARGET])
    result = replay_loop(ONE_STEP_LOOP, session, profit_target=1000)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason.startswith(player_mod.HALT_NEVER_AUTO_ACTION)  # gate outranks target
    assert session.sends == []


def test_target_and_floor_compose_the_floor_still_bites_under_a_healthy_target():
    session = TargetedSession(CLEAN_SCREENS, [UNDER_TARGET])

    class BothSession(TargetedNoSendSession):
        def credits(self):
            self.calls.append("credits")
            return sp.CreditsSnapshot(outcome=sp.OUTCOME_READ, balance=100, age_s=0.0)

    session = BothSession(CLEAN_SCREENS, [UNDER_TARGET])
    result = replay_loop(ONE_STEP_LOOP, session, floor=500, profit_target=1000)
    assert result.outcome == OUTCOME_HALTED
    assert result.reason == HALT_FLOOR_REACHED  # floor is checked first in the ladder


# ==========================================================================
# 3 -- entry refusal, mirroring the floor's arm-confirm rail
# ==========================================================================


def test_a_target_handed_to_a_port_that_cannot_observe_profit_is_refused_at_entry():
    session = ScriptedSession(CLEAN_SCREENS)  # no `profit()`
    assert not hasattr(session, "profit")
    with pytest.raises(TypeError, match="cannot observe profit"):
        replay_loop(ONE_STEP_LOOP, session, profit_target=1000)
    assert session.calls == []
    assert session.sends == []
    assert replay_loop(ONE_STEP_LOOP, session).outcome == OUTCOME_COMPLETED


@pytest.mark.parametrize("bad", [True, False, 500.0, "500", object()])
def test_a_target_that_is_not_an_int_is_refused_at_entry(bad):
    session = TargetedNoSendSession(CLEAN_SCREENS, [UNDER_TARGET])
    with pytest.raises(TypeError, match="must be an int"):
        replay_loop(ONE_STEP_LOOP, session, profit_target=bad)
    assert session.calls == []


@pytest.mark.parametrize("bad", [0, -1])
def test_a_profit_window_that_never_expires_is_refused(bad):
    session = TargetedNoSendSession(CLEAN_SCREENS, [UNDER_TARGET])
    with pytest.raises(ValueError, match="must be positive"):
        replay_loop(ONE_STEP_LOOP, session, profit_target=1000, profit_stale_ms=bad)
    assert session.calls == []


# ==========================================================================
# 4 -- AutoLoop wire: arm-time refusal + report round-trip
# ==========================================================================


class ProfitWireSession(WireSession):
    """The real `Session.observe_credits`/`profit_snapshot` bound off the
    class -- `observe_credits` is what fills BOTH the balance and the
    profit delta (see `Session.observe_credits`), so this is the one
    fake shape that legitimately answers `profit()`."""

    observe_credits = Session.observe_credits
    profit_snapshot = Session.profit_snapshot

    def __init__(self, screens, **kwargs):
        super().__init__(screens, **kwargs)
        self.credits_baseline = None
        self.last_credits = None
        self.last_credits_ts = None
        self.last_profit = None
        self.last_profit_ts = None


def _screen_with(body: str) -> str:
    """A real settled `main_command` screen carrying `body` above the
    prompt, mirroring `test_credits_floor.py`'s own helper -- so a balance
    read here is read off the same shape a live run actually sees."""
    return f"{body}\n{ANCHOR_158[0]}"


BALANCE_START = "You have 100,000 credits."
BALANCE_UP = "You have 101,500 credits."


def test_the_wire_accepts_a_profit_target_and_the_report_carries_the_number(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = ProfitWireSession([_screen_with(BALANCE_START), _screen_with(BALANCE_START)])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "profit_target": 1000}, server
    )
    assert resp["ok"] is True
    assert resp["run"]["profit_target"] == 1000
    run_to_completion(server.autoloop, session)

    status = protocol.dispatch(session, "autoloop_status", {}, server)
    assert status["run"]["profit_target"] == 1000
    assert status["run"]["outcome"] == "completed"


def test_an_untargeted_run_reports_a_null_profit_target(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = ProfitWireSession([_screen_with(BALANCE_START), _screen_with(BALANCE_START)])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(session, "autoloop_start", {"name": "ore-run"}, server)
    assert resp["run"]["profit_target"] is None
    run_to_completion(server.autoloop, session)
    assert protocol.dispatch(session, "autoloop_status", {}, server)["run"][
        "outcome"
    ] == "completed"


def test_a_profit_targeted_run_halts_once_the_target_is_crossed(tmp_path):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    # First balance seen becomes the baseline (profit 0); the second states
    # a balance 1,500cr above it -- past a 1,000cr target.
    session = ProfitWireSession([_screen_with(BALANCE_START), _screen_with(BALANCE_UP)])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "profit_target": 1000}, server
    )
    assert resp["ok"] is True
    run_to_completion(server.autoloop, session)

    status = protocol.dispatch(session, "autoloop_status", {}, server)
    assert status["run"]["outcome"] == "halted"
    assert status["run"]["reason"] == HALT_PROFIT_TARGET_REACHED


def test_a_targeted_run_against_a_port_that_cannot_observe_profit_is_refused(tmp_path):
    """`AutoLoopRunner.start` refuses BEFORE arming, mirroring `floor_
    unsupported` -- checked against the session's real ability to observe,
    never satisfiable by merely asserting a flag."""
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = WireSession([_screen_with(BALANCE_START)])  # no observe_credits/profit_snapshot
    assert not hasattr(session, "profit_snapshot")
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "profit_target": 1000}, server
    )
    assert resp == {"ok": False, "error": "profit_target_unsupported"}


@pytest.mark.parametrize("bad", [True, 500.0, "1000"])
def test_an_invalid_profit_target_is_refused_at_the_wire(tmp_path, bad):
    write_macro(tmp_path, "ore-run", ONE_STEP)
    session = ProfitWireSession([_screen_with(BALANCE_START)])
    lock = ControlLock()
    server = Server(session, lock, make_runner(tmp_path, session, lock))

    resp = protocol.dispatch(
        session, "autoloop_start", {"name": "ore-run", "profit_target": bad}, server
    )
    assert resp == {"ok": False, "error": "invalid_profit_target"}


def test_the_arg_vocabulary_carries_profit_target():
    """Pinned as a set, mirroring the floor/turn_budget pin: a future arg
    has to be argued for here as well as wired."""
    assert "profit_target" in autoloop.ARGS_AUTOLOOP_START


# ==========================================================================
# 5 -- TradeCaps: the default is a genuine no-op
# ==========================================================================


def test_trade_caps_profit_target_defaults_to_none():
    from tw2002_aiclient.session.trade_chain import TradeCaps

    caps = TradeCaps(cash_floor=1000, turn_reserve=10)
    assert caps.profit_target is None


def test_trade_chain_args_vocabulary_carries_profit_target():
    from tw2002_aiclient.session.trade_chain import ARGS_TRADE_CHAIN_START

    assert "profit_target" in ARGS_TRADE_CHAIN_START
