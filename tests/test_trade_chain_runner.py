import threading
from types import SimpleNamespace

import pytest

from tw2002_aiclient.chains import ProfitChain, TradeHop
from tw2002_aiclient.session.control_lock import ControlLock
from tw2002_aiclient.session.state_parser import OUTCOME_READ
from tw2002_aiclient.session import trade_chain
from tw2002_aiclient.trade_chain_plan import plan_from_chain
from tw2002_aiclient.trade_driver import ChainRunResult


def _chain(commodity="Fuel Ore"):
    hops = (
        TradeHop(1, 2, commodity, 10.0, 1),
        TradeHop(2, 1, "Equipment", 9.0, 1),
    )
    return ProfitChain((1, 2, 1), hops, 19.0, 2, 9.5, 19.0)


class _Session:
    def turns_snapshot(self):
        return SimpleNamespace(outcome=OUTCOME_READ, turns=100, age_s=0.0)


def _discovered(*chains, truncated=False):
    return SimpleNamespace(chains=chains, truncated=truncated)


def test_start_refuses_stale_identity_before_lock_or_thread(monkeypatch):
    chain = _chain()
    monkeypatch.setattr(
        trade_chain.chain_search,
        "recompute",
        lambda *a, **k: _discovered(_chain("Organics")),
    )
    lock = ControlLock()
    runner = trade_chain.TradeChainRunner(_Session(), lock)

    with pytest.raises(trade_chain.TradeChainRefused, match="chain_identity_stale"):
        runner.start("world-a", plan_from_chain("world-a", chain).fingerprint)

    assert runner.snapshot().running is False
    assert lock.is_auto_loop_held() is False


def test_start_refuses_truncated_empty_discovery(monkeypatch):
    """Soft partial gate: truncated with zero cycles still blocks start."""
    chain = _chain()
    monkeypatch.setattr(
        trade_chain.chain_search,
        "recompute",
        lambda *a, **k: _discovered(truncated=True),
    )
    runner = trade_chain.TradeChainRunner(_Session(), ControlLock())

    with pytest.raises(trade_chain.TradeChainRefused, match="chain_discovery_partial"):
        runner.start("world-a", plan_from_chain("world-a", chain).fingerprint)


def test_start_allows_truncated_discovery_when_exact_identity_is_present(monkeypatch):
    """RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES: exact fingerprint in a partial
    list may arm — absence of a *better* cycle is not established, but the
    selected cycle is."""
    chain = _chain()
    plan = plan_from_chain("world-a", chain)
    monkeypatch.setattr(
        trade_chain.chain_search,
        "recompute",
        lambda *a, **k: _discovered(chain, truncated=True),
    )
    ran = {"n": 0}

    def _run(_session, resolved, **kwargs):
        ran["n"] += 1
        assert resolved is chain
        return ChainRunResult(
            outcome=trade_chain.OUTCOME_COMPLETED,
            reason=None,
            hops_completed=2,
            sends_issued=4,
            credits_delta=10,
        )

    monkeypatch.setattr(trade_chain, "run_chain", _run)
    runner = trade_chain.TradeChainRunner(_Session(), ControlLock())
    snap = runner.start("world-a", plan.fingerprint)
    assert snap.running is True
    runner.stop()
    assert ran["n"] == 1


def test_exact_start_runs_once_and_stop_reaches_abort_predicate(monkeypatch):
    chain = _chain()
    plan = plan_from_chain("world-a", chain)
    entered = threading.Event()

    monkeypatch.setattr(
        trade_chain.chain_search,
        "recompute",
        lambda *a, **k: _discovered(chain),
    )

    def _run(_session, resolved, **kwargs):
        assert resolved is chain
        assert kwargs["world_id"] == "world-a"
        assert kwargs["caps"].cash_floor == 2_000
        assert kwargs["caps"].turn_reserve == 12
        kwargs["on_progress"](
            {
                "kind": "chain_progress",
                "hop_index": 0,
                "hops_total": 2,
                "steps": 7,
                "done": False,
                "stop_reason": None,
            }
        )
        entered.set()
        assert kwargs["is_armed"]() is True
        assert kwargs["should_abort"]() is False
        while not kwargs["should_abort"]():
            threading.Event().wait(0.005)
        return ChainRunResult(False, 0, 3, 0, "aborted")

    monkeypatch.setattr(trade_chain, "run_chain", _run)
    lock = ControlLock()
    runner = trade_chain.TradeChainRunner(_Session(), lock)

    snapshot = runner.start(
        "world-a",
        plan.fingerprint,
        cash_floor=2_000,
        turn_reserve=12,
    )
    assert entered.wait(1.0)
    assert snapshot.running is True
    live = runner.snapshot()
    assert live.report.hops_completed == 1
    assert live.report.sends_issued == 7
    assert lock.is_auto_loop_held() is True

    stopped = runner.stop(join_timeout=1.0)

    assert stopped.running is False
    assert stopped.report.outcome == "halted"
    assert stopped.report.reason == "aborted"
    assert stopped.report.stop_requested is True
    assert lock.is_auto_loop_held() is False


def test_unknown_turns_halts_without_invoking_driver(monkeypatch):
    chain = _chain()
    plan = plan_from_chain("world-a", chain)
    monkeypatch.setattr(
        trade_chain.chain_search, "recompute", lambda *a, **k: _discovered(chain)
    )
    monkeypatch.setattr(
        trade_chain,
        "run_chain",
        lambda *a, **k: pytest.fail("driver must not run without turns"),
    )

    class _NoTurns:
        def turns_snapshot(self):
            return SimpleNamespace(outcome="absent")

    runner = trade_chain.TradeChainRunner(_NoTurns(), ControlLock())
    runner.start("world-a", plan.fingerprint)
    if runner._thread is not None:
        runner._thread.join(1.0)
    report = runner.snapshot().report

    assert report.outcome == "halted"
    assert report.reason == "turns_unknown"
    assert report.sends_issued == 0
