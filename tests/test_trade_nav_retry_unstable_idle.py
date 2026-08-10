"""WO-DIAGNOSE-TRADE-CHAIN-UNCONFIRMED-SEND-HALT: trade `_navigate` must
pass retry_unstable_idle=True on sector warps so mid-paint byte races
do not ChainHold unconfirmed_send after the hop already landed."""

from __future__ import annotations

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import known_graph
from tw2002_aiclient.trade_driver import TradeDriverConfig, _StepCtx, _navigate
import tw2002_aiclient.trade_driver as trade_driver


def _cmd(sector: int, warps) -> str:
    warp_text = " - ".join(f"({w})" for w in warps)
    return (
        f"Sector  : {sector} in uncharted space.\n"
        f"Warps to Sector(s) :  {warp_text}\n"
        f"\n"
        f"Command [TL=00:00:08]:[{sector}] (?=Help)? : "
    )


class _NavSession:
    def __init__(self):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -10.0
        self.sent = []
        self._pending = False
        self._screen = _cmd(1, [2])

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending:
            self._pending = False
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._screen.split("\n")

    def render_text(self, rows=None):
        return "\n".join(rows) if rows is not None else self._screen

    def send(self, text, enter=True, secret=False):
        self.sent.append((text, enter, secret))
        if text.strip() == "2":
            self._screen = _cmd(2, [1])
        self._pending = True


class _Caps:
    turn_reserve = 0


def test_navigate_passes_retry_unstable_idle_on_sector_warp(tmp_path, monkeypatch):
    world_id = "nav-retry-unstable"
    world_model.upsert_sector(world_id, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path)
    world_model.upsert_sector(world_id, {"sector_id": 2, "warps": [1]}, state_dir=tmp_path)
    graph = known_graph(world_id, state_dir=tmp_path)

    captured = []

    def _spy(session, text, *, profile, confirm_prompt=None, enter=True, secret=False, **kwargs):
        captured.append({"text": text, "profile": profile, "confirm_prompt": confirm_prompt, **kwargs})
        session.send(text, enter=enter, secret=secret)
        return ("idle", 0.05, True)

    monkeypatch.setattr(trade_driver, "send_and_confirm_for", _spy)

    session = _NavSession()
    ctx = _StepCtx(session, TradeDriverConfig(step_timeout_s=2.0), lambda: False, lambda: True)
    left = _navigate(ctx, graph, 1, 2, turns_budget=10, caps=_Caps(), hop_index=0)
    assert left == 9
    warp_calls = [c for c in captured if str(c.get("text", "")).isdigit()]
    assert warp_calls, f"expected a sector warp send, got {captured!r}"
    # Nav warps map retry_unstable_idle=True → profile warp_unstable.
    assert warp_calls[0]["profile"] == "warp_unstable"
