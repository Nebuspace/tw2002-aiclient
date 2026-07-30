from types import SimpleNamespace

from tw2002_aiclient import adapters
from tw2002_aiclient.session import protocol
from tw2002_aiclient.session.trade_chain import (
    TradeChainRefused,
    TradeRunReport,
    TradeSnapshot,
)


class _Runner:
    def __init__(self):
        self.calls = []
        self.current = TradeSnapshot(running=False)

    def start(self, world_id, fingerprint, **kwargs):
        self.calls.append(("start", world_id, fingerprint, kwargs))
        if fingerprint == "f" * 64:
            raise TradeChainRefused("chain_identity_stale")
        self.current = TradeSnapshot(
            running=True,
            report=TradeRunReport(
                world_id=world_id,
                fingerprint=fingerprint,
                route="1>2>1",
                commodities=("Fuel Ore", "Equipment"),
                cash_floor=kwargs["cash_floor"],
                turn_reserve=kwargs["turn_reserve"],
                started_at="now",
                hops_total=2,
            ),
        )
        return self.current

    def stop(self):
        self.calls.append(("stop",))
        self.current = TradeSnapshot(running=False, report=self.current.report)
        return self.current

    def snapshot(self):
        return self.current


def test_protocol_start_forwards_exact_identity_and_both_floors():
    runner = _Runner()
    server = SimpleNamespace(trade_chain=runner)
    fingerprint = "a" * 64

    response = protocol.dispatch(
        None,
        "trade_chain_start",
        {
            "world_id": "world-a",
            "fingerprint": fingerprint,
            "cash_floor": 2_000,
            "turn_reserve": 12,
        },
        server,
    )

    assert response["ok"] is True
    assert response["running"] is True
    assert response["run"]["fingerprint"] == fingerprint
    assert runner.calls == [
        (
            "start",
            "world-a",
            fingerprint,
            {"cash_floor": 2_000, "turn_reserve": 12},
        )
    ]


def test_protocol_refuses_unknown_arg_and_stale_identity():
    runner = _Runner()
    server = SimpleNamespace(trade_chain=runner)

    unsupported = protocol.dispatch(
        None,
        "trade_chain_start",
        {"world_id": "world-a", "fingerprint": "a" * 64, "force": True},
        server,
    )
    stale = protocol.dispatch(
        None,
        "trade_chain_start",
        {"world_id": "world-a", "fingerprint": "f" * 64},
        server,
    )

    assert unsupported == {"ok": False, "error": "unsupported_arg:force"}
    assert stale == {"ok": False, "error": "chain_identity_stale"}
    assert runner.calls == [("start", "world-a", "f" * 64, {})]


def test_protocol_stop_and_status_are_typed_and_idempotent():
    runner = _Runner()
    server = SimpleNamespace(trade_chain=runner)

    stopped = protocol.dispatch(None, "trade_chain_stop", {}, server)
    status = protocol.dispatch(None, "trade_chain_status", {}, server)

    assert stopped == {"ok": True, "stopping": True, "running": False}
    assert status == {"ok": True, "running": False}
    assert runner.calls == [("stop",)]


def test_adapters_send_only_the_guarded_chain_verbs(monkeypatch, tmp_path):
    calls = []

    def _send(verb, args, **kwargs):
        calls.append((verb, args, kwargs))
        return {"ok": True, "running": verb == "trade_chain_start"}

    monkeypatch.setattr(adapters._cli, "send_request", _send)

    start = adapters.trade_chain_start(
        "world-a",
        "a" * 64,
        cash_floor=2_000,
        turn_reserve=12,
        run_dir=tmp_path,
    )
    stop = adapters.trade_chain_stop(run_dir=tmp_path)
    status = adapters.trade_chain_status(run_dir=tmp_path)

    assert start.ok and stop.ok and status.ok
    assert [call[0] for call in calls] == [
        "trade_chain_start",
        "trade_chain_stop",
        "trade_chain_status",
    ]
    assert calls[0][1] == {
        "world_id": "world-a",
        "fingerprint": "a" * 64,
        "cash_floor": 2_000,
        "turn_reserve": 12,
    }
