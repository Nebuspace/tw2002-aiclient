"""WO-AUDIT-COCKPIT-UTF8-GETCH — one physical UTF-8 keypress must not
become N forwarded game bytes.

Pty-proven defect (F9): U+2192 → getch ``[226, 134, 146]``, all three
``< 256``, all three forwarded via the old ``0 <= key < 256`` branch.

Hub-ruled contract: refuse multi-byte UTF-8 (lead ``0xC0``–``0xF4`` +
consume continuations) · tell on status_line · keep session alive · pure
ASCII notice naming ``U+XXXX`` never glyph · bare single-byte ``0x80``–
``0xFF`` still forwards · ``key >= 256`` path untouched.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import curses

from tw2002_aiclient import adapters, app
from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow

from .conftest import _FakeDaemon


class _RecordingStdscr:
    def __init__(self, keys):
        self._keys = list(keys)
        self.calls: list[tuple[int, int, str, int]] = []

    def getch(self):
        return self._keys.pop(0) if self._keys else -1

    def ungetch(self, ch):
        self._keys.insert(0, ch)

    def timeout(self, _ms):
        return None

    def getmaxyx(self):
        return (40, 160)

    def erase(self):
        return None

    def addstr(self, y, x, text, attr=0):
        self.calls.append((y, x, text, attr))

    def refresh(self):
        return None


def _profile() -> ProfileRow:
    return ProfileRow(
        name="t",
        handle="h",
        server="s",
        host="127.0.0.1",
        game_letter="A",
        autopilot=False,
        error=None,
    )


def _patch_common(monkeypatch):
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    monkeypatch.setattr(
        adapters,
        "ensure_session",
        lambda *a, **k: EnsureResult(ok=True, classification="main_command"),
    )


def _capture_play_instances(monkeypatch):
    captured: list[PlayShellScreen] = []
    orig_init = PlayShellScreen.__init__

    def _spy(self, *a, **k):
        orig_init(self, *a, **k)
        captured.append(self)

    monkeypatch.setattr(PlayShellScreen, "__init__", _spy)
    return captured


def _short_run_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="twd-utf8-"))


def test_utf8_multibyte_len_classifies_leads_only():
    assert app._utf8_multibyte_len(0x41) is None
    assert app._utf8_multibyte_len(0x80) is None
    assert app._utf8_multibyte_len(0xBF) is None
    assert app._utf8_multibyte_len(0xC0) == 2
    assert app._utf8_multibyte_len(0xE2) == 3
    assert app._utf8_multibyte_len(0xF4) == 4
    assert app._utf8_multibyte_len(0xF5) is None


def test_refuse_utf8_notice_is_ascii_codepoint_never_glyph():
    class _Std:
        def __init__(self, keys):
            self._keys = list(keys)

        def getch(self):
            return self._keys.pop(0) if self._keys else -1

    notice = app._refuse_utf8_getch_sequence(_Std([0x86, 0x92]), 0xE2)
    assert notice == "unencodable keystroke U+2192 - not sent"
    assert "→" not in notice
    assert all(ord(c) < 128 for c in notice)


def test_run_play_refuses_utf8_arrow_forwards_zero_bytes_keeps_session(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _RecordingStdscr([app.MODE_KEY, 0xE2, 0x86, 0x92, 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"
        assert daemon.session.raw_sent == []
        play = captured[-1]
        assert play.attached is True
        assert "U+2192" in play.status_line
        assert "not sent" in play.status_line
        assert "→" not in play.status_line
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_lone_lead_then_timeout_then_ascii_still_reaches_game(monkeypatch):
    """REVISE: truncated lead must not swallow the next real keystroke.

    Sequence: attach · lone UTF-8 lead · getch timeout (-1) · ordinary ``z`` · Esc.
    ``z`` must appear in ``raw_sent``.
    """
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)
        captured = _capture_play_instances(monkeypatch)

        stdscr = _RecordingStdscr([app.MODE_KEY, 0xE2, -1, ord("z"), 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"
        assert daemon.session.raw_sent == [b"z"]
        play = captured[-1]
        assert "not sent" in play.status_line
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_lone_lead_then_ascii_ungetch_still_forwards(monkeypatch):
    """REVISE: non-continuation after lead is ungetch'd, not dropped."""
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)

        # Lead then immediately ASCII 'q' (no continuation bytes)
        stdscr = _RecordingStdscr([app.MODE_KEY, 0xE2, ord("q"), 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"
        assert daemon.session.raw_sent == [b"q"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_still_forwards_bare_high_latin1_byte(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)

        stdscr = _RecordingStdscr([app.MODE_KEY, 0xA9, 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"
        assert daemon.session.raw_sent == [b"\xa9"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)


def test_run_play_ascii_and_key_ge_256_unchanged(monkeypatch):
    run_dir = _short_run_dir()
    daemon = _FakeDaemon(run_dir / "twd.sock")
    daemon.start()
    try:
        monkeypatch.setenv("TW_RUN_DIR", str(run_dir))
        _patch_common(monkeypatch)

        stdscr = _RecordingStdscr([app.MODE_KEY, ord("x"), curses.KEY_LEFT, 27])
        result = app._run_play(stdscr, _profile())
        assert result == "back"
        assert daemon.session.raw_sent == [b"x"]
    finally:
        daemon.stop()
        shutil.rmtree(run_dir, ignore_errors=True)
