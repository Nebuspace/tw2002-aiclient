"""WO-CLIENT-DAEMON-OWNERSHIP — lifecycle/presence unit pins.

Exact profile ONLINE mapping, bounded never-raising status/stop wrappers,
and default-No quit confirm wording/key posture.
"""

from __future__ import annotations

from pathlib import Path

import curses
import pytest

from tw2002_aiclient import daemon_lifecycle as life
from tw2002_aiclient.screens import LauncherScreen, ProfileRow


def _row(name: str, **kw) -> ProfileRow:
    return ProfileRow(
        name=name,
        handle=name.title(),
        server="demo",
        host="demo.example",
        game_letter="A",
        **kw,
    )


# --------------------------------------------------------------------------
# Presence mapping (exact match only)
# --------------------------------------------------------------------------


def test_online_requires_connected_and_exact_profile(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    monkeypatch.setattr(
        life._cli,
        "send_request",
        lambda *a, **k: {
            "ok": True,
            "connected": True,
            "replay_arm": {"armed": True, "profile": "alpha", "host": "h", "port": 23},
        },
    )
    p = life.read_presence()
    assert p.kind == life.PRESENCE_ONLINE
    assert p.profile == "alpha"
    assert life.is_profile_online(p, "alpha")
    assert not life.is_profile_online(p, "beta")
    assert not life.is_profile_online(p, "Alpha")  # exact, not case-folded


def test_connected_false_never_marks_online(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    monkeypatch.setattr(
        life._cli,
        "send_request",
        lambda *a, **k: {
            "ok": True,
            "connected": False,
            "replay_arm": {"armed": True, "profile": "alpha"},
        },
    )
    p = life.read_presence()
    assert p.kind == life.PRESENCE_OFFLINE
    assert life.online_profile_name(p) is None


@pytest.mark.parametrize(
    "arm",
    [
        None,
        {},
        {"profile": None},
        {"profile": ""},
        {"profile": "   "},
        {"profile": 12},
    ],
)
def test_missing_or_invalid_profile_never_online(monkeypatch, arm):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    monkeypatch.setattr(
        life._cli,
        "send_request",
        lambda *a, **k: {"ok": True, "connected": True, "replay_arm": arm},
    )
    p = life.read_presence()
    assert p.kind == life.PRESENCE_OFFLINE
    assert life.online_profile_name(p) is None


def test_daemon_absent_is_offline(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: False)
    calls: list = []

    def _send(*a, **k):
        calls.append(1)
        raise AssertionError("no status request when daemon absent")

    monkeypatch.setattr(life._cli, "send_request", _send)
    p = life.read_presence()
    assert p.kind == life.PRESENCE_OFFLINE
    assert calls == []


def test_unreachable_status_never_marks_online(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    monkeypatch.setattr(
        life._cli,
        "send_request",
        lambda *a, **k: {"ok": False, "error": "connect_failed:x"},
    )
    p = life.read_presence()
    assert p.kind == life.PRESENCE_UNREACHABLE
    assert life.online_profile_name(p) is None
    assert "unavailable" in (life.presence_note(p) or "")


def test_read_presence_never_raises(monkeypatch):
    monkeypatch.setattr(
        life._cli,
        "daemon_alive",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    p = life.read_presence()
    assert p.kind == life.PRESENCE_UNREACHABLE


def test_status_timeout_is_bounded(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    seen: dict = {}

    def _send(verb, payload, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        return {"ok": True, "connected": False}

    monkeypatch.setattr(life._cli, "send_request", _send)
    life.read_presence(timeout=1.25)
    assert seen["timeout"] == 1.25
    assert life.STATUS_TIMEOUT_S <= 5.0


# --------------------------------------------------------------------------
# Stop wrapper
# --------------------------------------------------------------------------


def test_stop_daemon_issues_exactly_one_stop(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    wire: list = []

    def _send(verb, payload, **kwargs):
        wire.append(verb)
        return {"ok": True}

    monkeypatch.setattr(life._cli, "send_request", _send)
    result = life.stop_daemon()
    assert result.ok
    assert wire == ["stop"]


def test_stop_daemon_failure_is_typed_not_raised(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    monkeypatch.setattr(
        life._cli,
        "send_request",
        lambda *a, **k: {"ok": False, "error": "busy"},
    )
    result = life.stop_daemon()
    assert not result.ok
    assert result.reason == "busy"


def test_stop_when_already_down_is_ok(monkeypatch):
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: False)
    monkeypatch.setattr(
        life._cli,
        "send_request",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no wire")),
    )
    assert life.stop_daemon().ok


# --------------------------------------------------------------------------
# Quit confirm wording + key posture
# --------------------------------------------------------------------------


def test_quit_confirm_line_shape():
    assert (
        life.compose_quit_confirm_line("alpha")
        == "Stop daemon and disconnect alpha? y/N"
    )
    assert (
        life.compose_quit_confirm_line(None)
        == "Stop daemon and disconnect ?? y/N"
    )


def test_quit_confirm_only_y_confirms():
    assert life.resolve_quit_confirm_key(ord("y")) == life.CONFIRM
    assert life.resolve_quit_confirm_key(ord("Y")) == life.CONFIRM
    for key in (10, 13, curses.KEY_ENTER, 27, ord("n"), ord("N"), ord("q"), -1):
        assert life.resolve_quit_confirm_key(key) == life.CANCEL


# --------------------------------------------------------------------------
# Launcher ONLINE render (recording stdscr)
# --------------------------------------------------------------------------


class _RecordingStdscr:
    def __init__(self, rows: int = 24, cols: int = 100) -> None:
        self._rows = rows
        self._cols = cols
        self.lines: list[str] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def erase(self) -> None:
        self.lines = []

    def refresh(self) -> None:
        return None

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        while len(self.lines) <= y:
            self.lines.append("")
        row = self.lines[y].ljust(x)
        self.lines[y] = (row[:x] + text)[: self._cols]


def _patch_launcher_curses(monkeypatch) -> None:
    monkeypatch.setattr("tw2002_aiclient.screens.curses.has_colors", lambda: False)
    monkeypatch.setattr(
        "tw2002_aiclient.screens._TonePalette.attr",
        lambda self, tone: 0,
    )
    monkeypatch.setattr("tw2002_aiclient.screens._draw_chrome_box", lambda *a, **k: None)
    monkeypatch.setattr("tw2002_aiclient.screens._glyph_set", lambda: {"sel": ">"})


def test_launcher_draws_online_only_on_active_row(monkeypatch):
    _patch_launcher_curses(monkeypatch)
    stdscr = _RecordingStdscr()
    screen = LauncherScreen(
        stdscr,
        profiles=[_row("alpha", online=True), _row("beta", online=False)],
    )
    screen.draw()
    blob = "\n".join(screen.stdscr.lines)
    assert "ONLINE" in blob
    assert "status" in blob
    # Only one ONLINE token for the active row.
    assert blob.count("ONLINE") == 1
    alpha_line = next(line for line in screen.stdscr.lines if "alpha" in line and "Alpha" in line)
    beta_line = next(line for line in screen.stdscr.lines if "beta" in line and "Beta" in line)
    assert "ONLINE" in alpha_line
    assert "ONLINE" not in beta_line


def test_launcher_presence_note_for_unreachable(monkeypatch):
    _patch_launcher_curses(monkeypatch)
    stdscr = _RecordingStdscr()
    screen = LauncherScreen(stdscr, profiles=[_row("alpha")])
    screen.set_presence_note(life.presence_note(life.Presence(kind=life.PRESENCE_UNREACHABLE)))
    screen.draw()
    blob = "\n".join(screen.stdscr.lines)
    assert "daemon status unavailable" in blob
    assert "ONLINE" not in blob


def test_apply_presence_exact_match_only(monkeypatch):
    from tw2002_aiclient import app as app_mod

    _patch_launcher_curses(monkeypatch)
    monkeypatch.setattr(life._cli, "daemon_alive", lambda *a, **k: True)
    monkeypatch.setattr(
        life._cli,
        "send_request",
        lambda *a, **k: {
            "ok": True,
            "connected": True,
            "replay_arm": {"profile": "alpha"},
        },
    )
    screen = LauncherScreen(
        _RecordingStdscr(),
        profiles=[_row("alpha"), _row("beta")],
    )
    app_mod._apply_presence(screen)
    assert screen.profiles[0].online is True
    assert screen.profiles[1].online is False


def test_confirm_app_quit_no_daemon_exits_without_stop(monkeypatch):
    from tw2002_aiclient import app as app_mod

    _patch_launcher_curses(monkeypatch)
    monkeypatch.setattr(life, "should_confirm_quit_stop", lambda **k: False)
    stops: list = []
    monkeypatch.setattr(life, "stop_daemon", lambda **k: stops.append(1) or life.StopResult(ok=True))
    screen = LauncherScreen(_RecordingStdscr(), profiles=[_row("alpha")])
    assert app_mod._confirm_app_quit(_RecordingStdscr(), screen) is True
    assert stops == []


def test_confirm_app_quit_enter_leaves_daemon(monkeypatch):
    from tw2002_aiclient import app as app_mod

    _patch_launcher_curses(monkeypatch)
    monkeypatch.setattr(life, "should_confirm_quit_stop", lambda **k: True)
    monkeypatch.setattr(
        life,
        "read_presence",
        lambda **k: life.Presence(kind=life.PRESENCE_ONLINE, profile="alpha"),
    )
    stops: list = []
    monkeypatch.setattr(life, "stop_daemon", lambda **k: stops.append(1) or life.StopResult(ok=True))

    class _Keys(_RecordingStdscr):
        def __init__(self) -> None:
            super().__init__()
            self._keys = [10]  # Enter → default No

        def getch(self) -> int:
            return self._keys.pop(0) if self._keys else -1

        def timeout(self, _ms: int) -> None:
            return None

        def keypad(self, _flag: bool) -> None:
            return None

    screen = LauncherScreen(_Keys(), profiles=[_row("alpha", online=True)])
    assert app_mod._confirm_app_quit(_Keys(), screen) is True
    assert stops == []


def test_confirm_app_quit_y_stops_once(monkeypatch):
    from tw2002_aiclient import app as app_mod

    _patch_launcher_curses(monkeypatch)
    monkeypatch.setattr(life, "should_confirm_quit_stop", lambda **k: True)
    monkeypatch.setattr(
        life,
        "read_presence",
        lambda **k: life.Presence(kind=life.PRESENCE_ONLINE, profile="alpha"),
    )
    stops: list = []
    monkeypatch.setattr(
        life,
        "stop_daemon",
        lambda **k: stops.append(1) or life.StopResult(ok=True),
    )

    class _Keys(_RecordingStdscr):
        def __init__(self) -> None:
            super().__init__()
            self._keys = [ord("y")]

        def getch(self) -> int:
            return self._keys.pop(0) if self._keys else -1

        def timeout(self, _ms: int) -> None:
            return None

        def keypad(self, _flag: bool) -> None:
            return None

    screen = LauncherScreen(_Keys(), profiles=[_row("alpha", online=True)])
    assert app_mod._confirm_app_quit(_Keys(), screen) is True
    assert stops == [1]


def test_confirm_app_quit_stop_failure_stays_open(monkeypatch):
    from tw2002_aiclient import app as app_mod

    _patch_launcher_curses(monkeypatch)
    monkeypatch.setattr(life, "should_confirm_quit_stop", lambda **k: True)
    monkeypatch.setattr(
        life,
        "read_presence",
        lambda **k: life.Presence(kind=life.PRESENCE_ONLINE, profile="alpha"),
    )
    monkeypatch.setattr(
        life,
        "stop_daemon",
        lambda **k: life.StopResult(ok=False, reason="busy", detail="still held"),
    )
    monkeypatch.setattr(app_mod, "_apply_presence", lambda *a, **k: None)

    class _Keys(_RecordingStdscr):
        def __init__(self) -> None:
            super().__init__()
            self._keys = [ord("y")]

        def getch(self) -> int:
            return self._keys.pop(0) if self._keys else -1

        def timeout(self, _ms: int) -> None:
            return None

        def keypad(self, _flag: bool) -> None:
            return None

    screen = LauncherScreen(_Keys(), profiles=[_row("alpha", online=True)])
    assert app_mod._confirm_app_quit(_Keys(), screen) is False
    assert screen.presence_note is not None
    assert "stop failed" in screen.presence_note
