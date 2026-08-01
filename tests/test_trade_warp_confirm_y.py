"""WO-WARP-CONFIRM-Y: trade `_navigate` answers Y after intentional hop."""

from __future__ import annotations

from pathlib import Path

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import known_graph
from tw2002_aiclient.trade_driver import (
    TradeDriverConfig,
    _ALLOWED_LETTER_SENDS,
    _StepCtx,
    _navigate,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WARP_CONFIRM = (FIXTURES / "warp_confirm_prompt.txt").read_text(encoding="utf-8")

def _cmd(sector: int, warps) -> str:
    warp_text = " - ".join(f"({w})" for w in warps)
    return (
        f"Sector  : {sector} in uncharted space.\n"
        f"Warps to Sector(s) :  {warp_text}\n"
        f"\n"
        f"Command [TL=00:00:08]:[{sector}] (?=Help)? : "
    )

class _NavSession:
    """main_command → hop → warp_confirm → Y → main_command at dest."""

    def __init__(self):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -10.0
        self.sent = []
        self._pending = False
        self._phase = "src"
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
        key = text.strip()
        if self._phase == "src" and key == "2":
            self._screen = WARP_CONFIRM
            self._phase = "confirm"
        elif self._phase == "confirm" and key.upper() == "Y":
            self._screen = _cmd(2, [1])
            self._phase = "dst"
        self._pending = True

def test_allowed_letters_include_y_for_warp_confirm():
    assert "Y" in _ALLOWED_LETTER_SENDS
    assert "A" not in _ALLOWED_LETTER_SENDS

def test_navigate_sends_y_on_warp_confirm_after_hop(tmp_path):
    world_id = "nav-warp-y"
    world_model.upsert_sector(world_id, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path)
    world_model.upsert_sector(world_id, {"sector_id": 2, "warps": [1]}, state_dir=tmp_path)
    graph = known_graph(world_id, state_dir=tmp_path)
    session = _NavSession()
    ctx = _StepCtx(session, TradeDriverConfig(step_timeout_s=2.0), lambda: False, lambda: True)

    class Caps:
        turn_reserve = 0

    left = _navigate(ctx, graph, 1, 2, turns_budget=10, caps=Caps(), hop_index=0)
    letters = [t[0].strip() for t in session.sent]
    assert letters == ["2", "Y"]
    assert session.sent[1][1] is False  # enter=False for Y/N
    assert left == 9
