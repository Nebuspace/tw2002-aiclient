"""WO-PLAY-EXPLORE-VISIBLE (L4) — explore progress on Play status_line.

Polls mocked ``adapters.explore_status`` on the 1 Hz idle tick after a
successful explore arm start; no CLI ``tw explore status`` required.
"""

from __future__ import annotations

from tw2002_aiclient import adapters, app as app_mod


class _Result:
    def __init__(self, ok=True, classification="main_command", reason=None, detail=None):
        self.ok, self.classification, self.reason, self.detail = ok, classification, reason, detail


class _ExploreResult:
    def __init__(self, ok=True, reason=None, raw=None):
        self.ok, self.reason, self.detail, self.raw = ok, reason, None, raw


class _Stdscr:
    """Scripted keys; append Esc to exit. Use -1 for idle redraw ticks."""

    def __init__(self, keys):
        self._keys = list(keys) + [27]
        self.rows, self.cols = 40, 160

    def getmaxyx(self):
        return (self.rows, self.cols)

    def getch(self):
        return self._keys.pop(0) if self._keys else 27

    def timeout(self, ms):
        pass

    def erase(self):
        pass

    def refresh(self):
        pass

    def addstr(self, *a, **k):
        pass

    def addnstr(self, *a, **k):
        pass

    def attron(self, a):
        pass

    def attroff(self, a):
        pass

    def hline(self, *a, **k):
        pass

    def vline(self, *a, **k):
        pass

    def border(self, *a, **k):
        pass

    def chgat(self, *a, **k):
        pass

    def keypad(self, flag):
        pass

    def nodelay(self, flag):
        pass


def _wire(*, running=True, distinct=0, min_sectors=5, outcome=None, reason=None):
    run = {
        "distinct_sectors": distinct,
        "min_sectors": min_sectors,
        "outcome": outcome,
        "reason": reason,
    }
    return {"running": running, "run": run}


def _drive(monkeypatch, keys, *, status_snapshots=None, explore_start=None):
    """Run ``_run_play``; return (status_calls, screen)."""
    status_calls: list[object] = []
    snapshots = list(status_snapshots or [])

    monkeypatch.setattr(
        adapters,
        "ensure_session",
        lambda name, **kw: _Result(),
    )
    if explore_start is None:
        explore_start = _ExploreResult(ok=True)
    monkeypatch.setattr(
        adapters,
        "explore_start_for_profile",
        lambda profile, **kw: explore_start,
        raising=False,
    )

    def _status(**kw):
        status_calls.append(kw)
        if snapshots:
            raw = snapshots.pop(0)
            return _ExploreResult(ok=True, raw=raw)
        return _ExploreResult(ok=True, raw=_wire(running=False, outcome="completed", distinct=5))

    monkeypatch.setattr(adapters, "explore_status", _status, raising=False)

    seen = {}
    real_screen = app_mod.PlayShellScreen

    class _Spy(real_screen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            seen["screen"] = self

        def draw(self):
            pass

    monkeypatch.setattr(app_mod, "PlayShellScreen", _Spy)
    monkeypatch.setattr(app_mod.curses, "has_colors", lambda: False, raising=False)

    profile = app_mod.ProfileRow(
        name="alpha",
        handle="Alpha",
        server="demo-a",
        host="demo-a.example",
        game_letter="B",
    )
    try:
        app_mod._run_play(_Stdscr(keys), profile)
    except Exception:
        pass
    return status_calls, seen.get("screen")


def test_idle_tick_updates_status_line_while_explore_runs(monkeypatch) -> None:
    """Accept 1: in-progress explore shows sector count on status_line."""
    calls, screen = _drive(
        monkeypatch,
        [ord("E"), ord("y"), -1, -1],
        status_snapshots=[
            _wire(running=True, distinct=2, min_sectors=5, outcome=None),
            _wire(running=True, distinct=3, min_sectors=5, outcome=None),
            _wire(running=False, distinct=5, min_sectors=5, outcome="completed"),
        ],
    )
    assert len(calls) >= 1
    assert "explore 3/5" in (screen.status_line or "")


def test_terminal_completed_status_line(monkeypatch) -> None:
    """Accept 2: completed outcome — stable final line, not stuck on start text."""
    _calls, screen = _drive(
        monkeypatch,
        [ord("E"), ord("y"), -1],
        status_snapshots=[
            _wire(running=False, distinct=5, min_sectors=5, outcome="completed"),
        ],
    )
    assert screen.status_line == "explore completed (5)"


def test_terminal_halted_status_line(monkeypatch) -> None:
    _calls, screen = _drive(
        monkeypatch,
        [ord("E"), ord("y"), -1],
        status_snapshots=[
            _wire(
                running=False,
                distinct=2,
                min_sectors=5,
                outcome="halted",
                reason="explore_exhausted",
            ),
        ],
    )
    assert screen.status_line == "explore halted: explore_exhausted"


def test_terminal_crashed_status_line(monkeypatch) -> None:
    _calls, screen = _drive(
        monkeypatch,
        [ord("E"), ord("y"), -1],
        status_snapshots=[
            _wire(
                running=False,
                distinct=1,
                min_sectors=5,
                outcome="crashed",
                reason="explore_driver_error",
            ),
        ],
    )
    assert "explore halted: explore_driver_error" in (screen.status_line or "")


def test_no_explore_status_poll_when_explore_not_active(monkeypatch) -> None:
    """Accept 3: without a successful arm start, idle ticks do not poll."""
    calls, _screen = _drive(monkeypatch, [-1, -1, -1])
    assert calls == []


def test_no_explore_status_poll_after_failed_start(monkeypatch) -> None:
    calls, _screen = _drive(
        monkeypatch,
        [ord("E"), ord("y"), -1],
        explore_start=_ExploreResult(ok=False, reason="daemon_not_running"),
    )
    assert calls == []


def test_format_explore_status_line_unit() -> None:
    line, keep = app_mod._explore_status_line_from_wire(
        _wire(running=True, distinct=4, min_sectors=5, outcome=None),
        default_min_sectors=5,
    )
    assert line == "explore 4/5…"
    assert keep is True

    line, keep = app_mod._explore_status_line_from_wire(
        _wire(running=False, distinct=5, outcome="completed"),
        default_min_sectors=5,
    )
    assert line == "explore completed (5)"
    assert keep is False
