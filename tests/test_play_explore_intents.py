"""Explore intents under WO-PLAY-STRIP-POLICY-AUTO + WO-FIND-STARDOCK-TOGGLE.

`E` starts infinite Explore. Intent is find-StarDock when
``find_stardock_on`` (default ON), else map-fill. `O` may still raise a
confirm for an autonomy explore offer.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient import adapters, app as app_mod
from tw2002_aiclient import explore as explore_mod


class _Result:
    def __init__(self, ok=True, classification="main_command", reason=None, detail=None):
        self.ok, self.classification, self.reason, self.detail = ok, classification, reason, detail


class _ExploreResult:
    def __init__(self, ok=True, reason=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, None


class _Stdscr:
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


def _drive(monkeypatch, keys, *, spectating=False, before_keys=None):
    calls: list = []
    monkeypatch.setattr(adapters, "ensure_session", lambda name, **kw: _Result())

    def _explore_start(profile, **kw):
        calls.append(kw)
        return _ExploreResult()

    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore_start, raising=False)

    seen: dict = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            if spectating:
                self.spectating = True
            if before_keys is not None:
                before_keys(self)
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
    return calls, seen.get("screen")


E = ord("E")
F = ord("F")


def test_app_armed_ensure_runs_find_stardock_infinite(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [])
    assert len(calls) == 1
    assert calls[0].get("intent") == explore_mod.INTENT_FIND_STARDOCK
    assert calls[0].get("min_sectors") == app_mod._EXPLORE_POLICY_MIN_SECTORS == 0
    assert screen.gate_raises == []
    assert screen.find_stardock_on is True


def test_e_restarts_find_stardock_infinite(monkeypatch) -> None:
    calls, _screen = _drive(monkeypatch, [E])
    assert calls[-1].get("intent") == explore_mod.INTENT_FIND_STARDOCK
    assert calls[-1].get("min_sectors") == 0


def test_e_with_find_stardock_off_runs_map_fill(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch,
        [E],
        before_keys=lambda play: setattr(play, "find_stardock_on", False),
    )
    assert calls[-1].get("intent") == explore_mod.INTENT_MAP_FILL
    assert calls[-1].get("min_sectors") == 0
    assert screen.find_stardock_on is False


def test_f_then_e_flips_to_map_fill(monkeypatch) -> None:
    """Calm `F` toggles Find StarDock OFF before `E` starts Explore."""
    calls, screen = _drive(monkeypatch, [F, E])
    assert screen.find_stardock_on is False
    assert calls[-1].get("intent") == explore_mod.INTENT_MAP_FILL


def test_e_alone_never_raises_the_gate(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [E], spectating=True)
    assert len(calls) == 1
    assert screen.gate_raises == []


def test_the_armable_intents_are_a_closed_ordered_set():
    assert explore_mod.ARMABLE_INTENTS == (
        explore_mod.INTENT_MAP_FILL,
        explore_mod.INTENT_FIND_STARDOCK,
    )
    assert set(explore_mod.ARMABLE_INTENTS) <= explore_mod.INTENTS
    assert not hasattr(explore_mod, "next_armable_intent")


def test_play_confirm_arm_enforces_armable_intents_in_source():
    """Parity pin: Play confirm-arm must consult ARMABLE_INTENTS at runtime."""
    from pathlib import Path

    src = Path(explore_mod.__file__).resolve().parent / "app.py"
    text = src.read_text(encoding="utf-8")
    assert "armed_intent not in _explore.ARMABLE_INTENTS" in text
