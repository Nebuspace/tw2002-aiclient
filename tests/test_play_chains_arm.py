"""WO-EXPLORE-TRADE-MODE-SPLIT — L arms · T executes taught/discovered loops.

Drives the real `app._run_play` with a fake stdscr and mocked adapters.

States that matter (RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES):
  * `L` -> popup opens, NOTHING started and no gate raised
  * `L` then Enter -> arms `trade_loop_arm`, still nothing started (no y-gate)
  * `L` Enter `T` with Port Trade·ON -> autoloop_start / trade_chain_start
  * Enter alone never fires a launch
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient.loops import store as _loop_store


class _Result:
    def __init__(self, ok=True, classification="main_command", reason=None, detail=None):
        self.ok, self.classification, self.reason, self.detail = ok, classification, reason, detail


class _AutoLoopResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _ExploreResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _Stdscr:
    """Feeds a scripted key sequence, then Esc to leave the loop."""

    def __init__(self, keys):
        self._keys = list(keys) + [27, 27]
        self.rows, self.cols = 40, 180

    def getmaxyx(self): return (self.rows, self.cols)
    def getch(self): return self._keys.pop(0) if self._keys else 27
    def timeout(self, ms): pass
    def erase(self): pass
    def refresh(self): pass
    def addstr(self, *a, **k): pass
    def addnstr(self, *a, **k): pass
    def attron(self, a): pass
    def attroff(self, a): pass
    def hline(self, *a, **k): pass
    def vline(self, *a, **k): pass
    def border(self, *a, **k): pass
    def chgat(self, *a, **k): pass
    def keypad(self, flag): pass
    def nodelay(self, flag): pass


TWO_LOOPS = {
    "status": "ok",
    "loops": [
        {"name": "ore-run-K7", "steps": 12, "draft": False},
        {"name": "fuel-shuttle", "steps": 8, "draft": False},
    ],
}
EMPTY_OK = {"status": "ok", "loops": []}
UNREADABLE = {"status": "unreadable", "loops": []}


def _drive(monkeypatch, keys, *, store=None, started=None, raises=None, port_trade_on=True):
    """Run `_run_play`; return (arm_calls, explore_calls, screen)."""
    arm_calls: list = []
    explore_calls: list = []

    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())
    monkeypatch.setattr(
        _loop_store, "read_loop_store",
        (lambda **kw: (_ for _ in ()).throw(raises)) if raises is not None
        else (lambda **kw: TWO_LOOPS if store is None else store),
    )

    def _arm(name=None, **kw):
        arm_calls.append((name, kw))
        return started if started is not None else _AutoLoopResult()

    def _explore(profile, **kw):
        explore_calls.append(kw)
        return _ExploreResult()

    monkeypatch.setattr(adapters, "autoloop_start", _arm, raising=False)
    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)
    monkeypatch.setattr(adapters, "explore_stop", lambda **kw: _ExploreResult(), raising=False)
    monkeypatch.setattr(adapters, "autoloop_stop", lambda **kw: _AutoLoopResult(), raising=False)
    monkeypatch.setattr(adapters, "trade_chain_stop", lambda **kw: _AutoLoopResult(), raising=False)

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            self.spectating = True
            self.port_trade_on = port_trade_on
            seen["screen"] = self

        def begin_arm_confirm(self, action=None, *, cycles=None):
            self.gate_raises.append((action, cycles))
            return super().begin_arm_confirm(action, cycles=cycles)

        def draw(self):
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)

    profile = app_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr(keys), profile)
    except Exception:
        pass
    return arm_calls, explore_calls, seen.get("screen")


L = ord("L")
T = ord("T")
ENTER = 10
DOWN = 258  # curses.KEY_DOWN


def test_l_opens_the_popup_but_arms_nothing(monkeypatch) -> None:
    arm, explore, screen = _drive(monkeypatch, [L])
    assert arm == []
    assert explore == []
    assert screen.gate_raises == [], f"gate raised by merely opening: {screen.gate_raises}"
    assert screen.trade_loop_arm is None


def test_enter_arms_trade_loop_without_starting(monkeypatch) -> None:
    """L Enter arms selection; bare Enter must never fire a launch."""
    arm, _explore, screen = _drive(monkeypatch, [L, ENTER])
    assert arm == [], "Enter alone started a run"
    assert screen.gate_raises == [], "mode-split arms without y-gate"
    assert screen.trade_loop_arm == {"kind": "taught", "name": "ore-run-K7"}
    assert "press T to run" in (screen.status_line or "")


def test_l_enter_t_starts_the_selected_loop(monkeypatch) -> None:
    arm, explore, screen = _drive(monkeypatch, [L, ENTER, T])
    assert len(arm) == 1
    assert arm[0][0] == "ore-run-K7"
    assert explore == []


def test_t_with_port_trade_off_refuses(monkeypatch) -> None:
    arm, _explore, screen = _drive(monkeypatch, [L, ENTER, T], port_trade_on=False)
    assert arm == []
    assert "Port Trade" in (screen.status_line or "")


def test_t_without_arm_refuses(monkeypatch) -> None:
    arm, _explore, screen = _drive(monkeypatch, [T])
    assert arm == []
    assert "no Trade Loop armed" in (screen.status_line or "")


def test_starting_a_loop_does_not_start_explore(monkeypatch) -> None:
    arm, explore, _screen = _drive(monkeypatch, [L, ENTER, T])
    assert len(arm) == 1
    assert explore == [], f"Trade Loop start also started EXPLORE: {explore}"


def test_confirming_explore_does_not_arm_a_loop(monkeypatch) -> None:
    arm, explore, _screen = _drive(monkeypatch, [ord("E")])
    assert len(explore) == 1, "explore did not start"
    assert arm == [], f"an explore start armed a taught loop: {arm}"


def test_orphan_arm_confirm_starts_neither_runner(monkeypatch) -> None:
    arm_calls: list = []
    explore_calls: list = []
    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())
    monkeypatch.setattr(_loop_store, "read_loop_store", lambda **kw: TWO_LOOPS)

    def _arm(name=None, **kw):
        arm_calls.append((name, kw))
        return _AutoLoopResult()

    def _explore(profile, **kw):
        explore_calls.append(kw)
        return _ExploreResult()

    monkeypatch.setattr(adapters, "autoloop_start", _arm, raising=False)
    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._orphan_fired = False
            self.spectating = True
            seen["screen"] = self

        def handle_key(self, key):
            if key == ord("y") and not self._orphan_fired:
                self._orphan_fired = True
                return "arm_confirm"
            return super().handle_key(key)

        def draw(self):
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)
    profile = app_mod.ProfileRow(
        name="alpha", handle="Alpha", server="demo-a",
        host="demo-a.example", game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr([ord("y")]), profile)
    except Exception:
        pass
    assert arm_calls == [], f"orphan confirm started autoloop: {arm_calls}"
    assert explore_calls == [], f"orphan confirm started explore: {explore_calls}"
    assert "nothing pending" in (seen["screen"].status_line or "")


def test_explore_confirm_still_requires_explicit_pending(monkeypatch) -> None:
    arm, explore, _screen = _drive(monkeypatch, [ord("E")])
    assert explore and not arm
    src = Path(app_mod.__file__).read_text(encoding="utf-8")
    assert 'if action == "arm_confirm" and pending_confirm_action == "explore"' in src
    bare = src.split('if action == "arm_confirm":', 1)[1].split("if action ==", 1)[0]
    assert "explore_start" not in bare


def test_moving_the_cursor_arms_the_row_under_cursor(monkeypatch) -> None:
    arm, _explore, screen = _drive(monkeypatch, [L, DOWN, ENTER, T])
    assert len(arm) == 1
    assert arm[0][0] == "fuel-shuttle"
    assert screen.trade_loop_arm == {"kind": "taught", "name": "fuel-shuttle"}


def test_an_empty_store_arms_nothing(monkeypatch) -> None:
    arm, _explore, screen = _drive(monkeypatch, [L, ENTER], store=EMPTY_OK)
    assert arm == []
    assert screen.trade_loop_arm is None
    assert screen.gate_raises == []


def test_an_unreadable_store_is_not_reported_as_empty(monkeypatch) -> None:
    _arm, _explore, screen = _drive(monkeypatch, [L], store=UNREADABLE)
    assert screen.chains_session.status == "unreadable"


def test_a_raising_store_read_does_not_take_down_the_play_loop(monkeypatch) -> None:
    _arm, _explore, screen = _drive(monkeypatch, [L], raises=OSError("disk gone"))
    assert screen is not None
    assert screen.chains_session.status == "unreadable"
    assert "OSError" in (screen.status_line or "")


def test_a_daemon_refusal_is_surfaced_not_smoothed(monkeypatch) -> None:
    arm, _explore, screen = _drive(
        monkeypatch, [L, ENTER, T],
        started=_AutoLoopResult(ok=False, reason="locked_by_active_driver"),
    )
    assert len(arm) == 1
    assert "locked_by_active_driver" in (screen.status_line or "")


def test_bare_enter_never_starts_a_runner(monkeypatch) -> None:
    arm, _explore, screen = _drive(monkeypatch, [L, ENTER, ENTER])
    assert arm == []
    assert screen.trade_loop_arm == {"kind": "taught", "name": "ore-run-K7"}
