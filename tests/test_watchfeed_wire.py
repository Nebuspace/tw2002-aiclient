"""WO-P4-050 (wire lane) — WatchFeed lifecycle wired into the play shell.

Layer-A only: no pty, no real ``run/twd.sock``. ``app.WatchFeed`` is
monkeypatched with a recording double so these tests prove app.py's own
start/stop wiring, never ``watchfeed.py``'s internals (that's lane 1's
own ``tests/test_watchfeed.py``). Mirrors the ``_RecordingStdscr`` +
monkeypatched-``adapters.ensure_session`` idiom already established in
``tests/test_play_chrome_nav.py``.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.screens import ProfileRow

# Temporary sequencing guard (WO-P4-050, lane 2): lane 1 builds
# ``tw2002_aiclient/watchfeed.py`` concurrently and may not have landed on
# disk yet. This module never imports it directly -- ``app.py`` does, at
# ``import tw2002_aiclient.app`` time inside each test below -- so a
# missing module surfaces as an ImportError from THAT statement, not from
# collecting this file. Skip cleanly instead of erroring; once the real
# module lands this import starts succeeding and every test below runs
# for real with no further edit needed here.
pytest.importorskip(
    "tw2002_aiclient.watchfeed",
    reason="WO-P4-050 lane 1 (watchfeed.py) not yet landed -- sequencing, not a bug",
)


class _RecordingStdscr:
    """Minimal curses window for ``_run_play`` without a real TTY."""

    def __init__(self, keys: list[int], rows: int = 24, cols: int = 80) -> None:
        self._keys = list(keys)
        self._rows = rows
        self._cols = cols
        self.lines: list[str] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def erase(self) -> None:
        self.lines = []

    def clear(self) -> None:
        self.erase()

    def refresh(self) -> None:
        pass

    def keypad(self, _flag: bool) -> None:
        pass

    def timeout(self, _ms: int) -> None:
        pass

    def attron(self, _attr: int) -> None:
        pass

    def attroff(self, _attr: int) -> None:
        pass

    def box(self, *_a) -> None:
        pass

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        while len(self.lines) <= y:
            self.lines.append("")
        row = self.lines[y].ljust(x)
        self.lines[y] = (row[:x] + text)[: self._cols]

    def getch(self) -> int:
        if not self._keys:
            return ord("q")
        return self._keys.pop(0)


class _RecordingFeed:
    """Records construction kwargs + start/stop calls; never touches a socket."""

    instances: list["_RecordingFeed"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.start_calls = 0
        self.stop_calls = 0
        _RecordingFeed.instances.append(self)

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def snapshot(self):
        return None


@pytest.fixture(autouse=True)
def _reset_recording_feed():
    _RecordingFeed.instances.clear()
    yield
    _RecordingFeed.instances.clear()


def _profile() -> ProfileRow:
    return ProfileRow(
        name="alpha",
        handle="Alpha",
        server="demo-a",
        host="demo-a.example",
        game_letter="B",
    )


def _stub_ensure(monkeypatch):
    import tw2002_aiclient.adapters as adapters_mod

    monkeypatch.setattr(
        adapters_mod,
        "ensure_session",
        lambda profile, **kwargs: EnsureResult(ok=True, classification="main_command"),
    )
    monkeypatch.setattr(
        "tw2002_aiclient.screens.curses.has_colors",
        lambda: False,
    )


def test_enter_play_constructs_and_starts_exactly_one_feed(monkeypatch):
    import tw2002_aiclient.app as app_mod
    from tw2002_aiclient.session import env as session_env

    _stub_ensure(monkeypatch)
    monkeypatch.setattr(app_mod, "WatchFeed", _RecordingFeed)

    stdscr = _RecordingStdscr([27])  # Esc immediately
    result = app_mod._run_play(stdscr, _profile())

    assert result == "back"
    assert len(_RecordingFeed.instances) == 1
    feed = _RecordingFeed.instances[0]
    assert feed.start_calls == 1
    assert feed.kwargs.get("run_dir") == session_env.resolve_run_dir()


def test_esc_back_stops_feed_exactly_once(monkeypatch):
    import tw2002_aiclient.app as app_mod

    _stub_ensure(monkeypatch)
    monkeypatch.setattr(app_mod, "WatchFeed", _RecordingFeed)

    stdscr = _RecordingStdscr([27])
    result = app_mod._run_play(stdscr, _profile())

    assert result == "back"
    feed = _RecordingFeed.instances[0]
    assert feed.stop_calls == 1


def test_quit_from_play_stops_feed(monkeypatch):
    import tw2002_aiclient.app as app_mod

    _stub_ensure(monkeypatch)
    monkeypatch.setattr(app_mod, "WatchFeed", _RecordingFeed)

    stdscr = _RecordingStdscr([ord("q")])
    result = app_mod._run_play(stdscr, _profile())

    assert result == "quit"
    feed = _RecordingFeed.instances[0]
    assert feed.start_calls == 1
    assert feed.stop_calls == 1


def test_two_sequential_play_entries_start_and_stop_independent_feeds(monkeypatch):
    """Re-entering the play shell (back, then play again) starts a FRESH
    feed each time -- no leaked state, no double-stop of a stale instance."""
    import tw2002_aiclient.app as app_mod

    _stub_ensure(monkeypatch)
    monkeypatch.setattr(app_mod, "WatchFeed", _RecordingFeed)

    profile = _profile()
    first = app_mod._run_play(_RecordingStdscr([27]), profile)
    second = app_mod._run_play(_RecordingStdscr([27]), profile)

    assert first == "back"
    assert second == "back"
    assert len(_RecordingFeed.instances) == 2
    for feed in _RecordingFeed.instances:
        assert feed.start_calls == 1
        assert feed.stop_calls == 1


def test_exception_unwind_from_loop_still_stops_feed(monkeypatch):
    """A crashed play loop must still stop the feed (try/finally proof)."""
    import tw2002_aiclient.app as app_mod
    import tw2002_aiclient.screens as screens_mod

    _stub_ensure(monkeypatch)
    monkeypatch.setattr(app_mod, "WatchFeed", _RecordingFeed)

    class _Boom(Exception):
        pass

    def _boom_handle_key(self, key):
        raise _Boom("simulated crash mid-loop")

    monkeypatch.setattr(screens_mod.PlayShellScreen, "handle_key", _boom_handle_key)

    stdscr = _RecordingStdscr([ord("x")])
    with pytest.raises(_Boom):
        app_mod._run_play(stdscr, _profile())

    assert len(_RecordingFeed.instances) == 1
    feed = _RecordingFeed.instances[0]
    assert feed.start_calls == 1
    assert feed.stop_calls == 1
