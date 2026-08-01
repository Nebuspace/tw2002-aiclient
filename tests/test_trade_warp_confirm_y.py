"""WO-WARP-CONFIRM-Y (REVISE, hub reject of always-Y): trade `_navigate`
answers N + HOLDs on an avoid-DANGER warp_confirm after an intentional
hop; still Y on an ordinary (non-avoid) warp_confirm."""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import world_model
from tw2002_aiclient.explore import known_graph
from tw2002_aiclient.trade_driver import (
    ChainHold,
    TradeDriverConfig,
    _ALLOWED_LETTER_SENDS,
    _StepCtx,
    _navigate,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WARP_CONFIRM_AVOID = (FIXTURES / "warp_confirm_prompt.txt").read_text(encoding="utf-8")
WARP_CONFIRM_PLAIN = (FIXTURES / "warp_confirm_prompt_plain.txt").read_text(encoding="utf-8")

def _cmd(sector: int, warps) -> str:
    warp_text = " - ".join(f"({w})" for w in warps)
    return (
        f"Sector  : {sector} in uncharted space.\n"
        f"Warps to Sector(s) :  {warp_text}\n"
        f"\n"
        f"Command [TL=00:00:08]:[{sector}] (?=Help)? : "
    )

class _NavSession:
    """main_command → hop → warp_confirm (ordinary) → Y → main_command at dest."""

    def __init__(self, confirm_text=WARP_CONFIRM_PLAIN, confirm_answer="Y"):
        self.t = 0.0
        self.rx_count = 1
        self.last_rx = -10.0
        self.sent = []
        self._pending = False
        self._phase = "src"
        self._screen = _cmd(1, [2])
        self._confirm_text = confirm_text
        self._confirm_answer = confirm_answer

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
            self._screen = self._confirm_text
            self._phase = "confirm"
        elif self._phase == "confirm" and key.upper() == self._confirm_answer:
            self._screen = _cmd(2, [1])
            self._phase = "dst"
        self._pending = True

def _graph(tmp_path):
    world_id = "nav-warp-y"
    world_model.upsert_sector(world_id, {"sector_id": 1, "warps": [2]}, state_dir=tmp_path)
    world_model.upsert_sector(world_id, {"sector_id": 2, "warps": [1]}, state_dir=tmp_path)
    return known_graph(world_id, state_dir=tmp_path)

class _Caps:
    turn_reserve = 0

def test_allowed_letters_include_y_and_n_for_warp_confirm():
    assert "Y" in _ALLOWED_LETTER_SENDS
    assert "N" in _ALLOWED_LETTER_SENDS
    assert "A" not in _ALLOWED_LETTER_SENDS

def test_navigate_sends_y_on_warp_confirm_after_hop(tmp_path):
    graph = _graph(tmp_path)
    session = _NavSession(confirm_text=WARP_CONFIRM_PLAIN, confirm_answer="Y")
    ctx = _StepCtx(session, TradeDriverConfig(step_timeout_s=2.0), lambda: False, lambda: True)

    left = _navigate(ctx, graph, 1, 2, turns_budget=10, caps=_Caps(), hop_index=0)
    letters = [t[0].strip() for t in session.sent]
    assert letters == ["2", "Y"]
    assert session.sent[1][1] is False  # enter=False for Y/N
    assert left == 9

def test_navigate_sends_n_and_holds_on_avoid_danger_after_hop(tmp_path):
    """REVISE (hub reject of always-Y): avoid-DANGER body -> N, then HOLD
    this hop rather than loop back into the same avoided sector."""
    graph = _graph(tmp_path)
    session = _NavSession(confirm_text=WARP_CONFIRM_AVOID, confirm_answer="N")
    ctx = _StepCtx(session, TradeDriverConfig(step_timeout_s=2.0), lambda: False, lambda: True)

    with pytest.raises(ChainHold, match="avoid_declined:0:2"):
        _navigate(ctx, graph, 1, 2, turns_budget=10, caps=_Caps(), hop_index=0)
    letters = [t[0].strip() for t in session.sent]
    assert letters == ["2", "N"]
    assert session.sent[1][1] is False  # enter=False for Y/N
