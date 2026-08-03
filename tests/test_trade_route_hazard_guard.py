"""WO-TRADE-ROUTE-HAZARD-GUARD — ChainHold before one-way / warp-sink hops."""

from __future__ import annotations

import pytest

from tw2002_aiclient.trade_driver import (
    ChainHold,
    TradeDriverConfig,
    _StepCtx,
    _navigate,
)


class _Caps:
    turn_reserve = 0
    cash_floor = 0
    credits_stale_ms = 60_000


class _QuietSession:
    """Never reached for sends if the hazard guard fires first."""

    def __init__(self):
        self.sent = []
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -10.0

    def clock(self):
        return self.t

    def render(self):
        raise AssertionError("fresh() must not run after route-hazard HOLD")

    def render_text(self, rows):
        return ""

    def send(self, text, enter=True):
        self.sent.append(text)
        raise AssertionError(f"must not send on route hazard: {text!r}")


def test_navigate_holds_on_one_way_before_any_send():
    # 1→2 one-way (no reverse); path needs that edge.
    graph = {1: (2,), 2: (3,), 3: (2,)}
    session = _QuietSession()
    ctx = _StepCtx(
        session,
        TradeDriverConfig(),
        should_abort=lambda: False,
        is_armed=lambda: True,
    )
    with pytest.raises(ChainHold, match=r"route_hazard:one_way:1->2:0"):
        _navigate(ctx, graph, 1, 2, turns_budget=10, caps=_Caps(), hop_index=0)
    assert session.sent == []


def test_navigate_holds_on_warp_sink_membership():
    graph = {1: (2,), 2: (1,)}
    session = _QuietSession()
    ctx = _StepCtx(
        session,
        TradeDriverConfig(),
        should_abort=lambda: False,
        is_armed=lambda: True,
    )
    with pytest.raises(ChainHold, match=r"route_hazard:warp_sink:2:0"):
        _navigate(
            ctx,
            graph,
            1,
            2,
            turns_budget=10,
            caps=_Caps(),
            hop_index=0,
            membership={2: ("warp-sink",)},
        )
    assert session.sent == []
