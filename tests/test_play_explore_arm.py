"""WO-PLAY-EXPLORE-ARM / WO-PLAY-STRIP-POLICY-AUTO REVISE -- Play explore.

Trainer strip: after ensure on main_command, App-armed kicks infinite
find-StarDock explore (min_sectors=0). `E` restarts the same run without a
confirm gate. LOGS keeps the plain ready line until the kick overwrites it —
no press-E / GATHER_HINT tease.
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
        self._keys = list(keys) + [27]
        self.rows, self.cols = 40, 160

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


def _drive(monkeypatch, keys, *, ensure=None, explore=None, raises=None, spectating=False):
    """Run `_run_play`; return (explore_calls, screen).

    spectating=True skips the App-armed ensure kick (not APP-ARMED) while
    still leaving explore_offered when classification is main_command.
    """
    calls = []

    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda name, **kw: ensure if ensure is not None else _Result(),
    )

    def _explore(profile, **kw):
        calls.append(kw)
        if raises is not None:
            raise raises
        return explore if explore is not None else _ExploreResult()

    monkeypatch.setattr(adapters, "explore_start_for_profile", _explore, raising=False)

    seen = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.gate_raises = []
            if spectating:
                self.spectating = True
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


def test_ensure_success_does_not_paint_explore_offer_tease(monkeypatch) -> None:
    """LOGS must not advertise press-E / GATHER_HINT after ensure."""
    calls, screen = _drive(monkeypatch, [])
    line = screen.status_line or ""
    assert "press E" not in line, line
    assert "D to pass" not in line, line
    assert "explore available" not in line, line
    # App-armed kick replaces ready with policy status
    assert calls and calls[0]["min_sectors"] == app_mod._EXPLORE_POLICY_MIN_SECTORS == 0
    assert calls[0].get("intent") == explore_mod.INTENT_FIND_STARDOCK


def test_app_armed_ensure_kicks_infinite_explore(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [])
    assert len(calls) == 1
    assert calls[0]["min_sectors"] == 0
    assert calls[0].get("intent") == explore_mod.INTENT_FIND_STARDOCK
    assert screen.gate_raises == []
    assert "infinite" in (screen.status_line or "").lower() or "StarDock" in (screen.status_line or "")


def test_e_restarts_infinite_explore_without_confirm(monkeypatch) -> None:
    calls, screen = _drive(monkeypatch, [ord("E")])
    assert len(calls) >= 2  # ensure kick + E restart
    assert calls[-1]["min_sectors"] == 0
    assert calls[-1].get("intent") == explore_mod.INTENT_FIND_STARDOCK
    assert screen.gate_raises == []


def test_e_starts_infinite_when_not_app_armed(monkeypatch) -> None:
    """Spectating skips ensure kick; E still starts policy explore."""
    calls, screen = _drive(monkeypatch, [ord("E")], spectating=True)
    assert len(calls) == 1
    assert calls[0]["min_sectors"] == 0
    assert calls[0].get("intent") == explore_mod.INTENT_FIND_STARDOCK
    assert screen.gate_raises == []


def test_e_does_nothing_when_no_offer_is_standing(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch, [ord("E")],
        ensure=_Result(ok=True, classification="unknown"),
        spectating=True,
    )
    assert calls == []
    assert screen.gate_raises == []


def test_no_offer_when_ensure_failed(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch, [ord("E")],
        ensure=_Result(ok=False, classification=None, reason="login_stalled", detail="x"),
    )
    assert calls == [], "explore offered after a failed ensure"
    assert "ensure failed" in (screen.status_line or "")


def test_gate_is_not_raised_unbidden_on_ensure(monkeypatch) -> None:
    _calls, screen = _drive(monkeypatch, [])
    assert screen.gate_raises == [], screen.gate_raises


def test_explore_start_failure_is_contained(monkeypatch) -> None:
    secret = "hunter2-not-for-logs"
    calls, screen = _drive(monkeypatch, [], raises=RuntimeError(secret))
    assert "explore failed" in (screen.status_line or "")
    assert secret not in (screen.status_line or "")


def test_adapter_refusal_is_surfaced(monkeypatch) -> None:
    calls, screen = _drive(
        monkeypatch, [],
        explore=_ExploreResult(ok=False, reason="already_running"),
    )
    assert "already_running" in (screen.status_line or "")
