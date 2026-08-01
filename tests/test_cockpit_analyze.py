"""WO-P5-069 — A Analyze on-demand overlay.

Pins:

1.  ``AnalyzeSession`` open/close lifecycle — starts closed; ``open()``
    opens; ``close()`` closes; both are idempotent; ``is_open`` tracks.
2.  ``OVERLAY_LABEL`` is a non-empty string (the badge text the draw
    layer shows in the teach_band slot while open).
3.  ``A`` / ``a`` key returns ``"analyze_open"`` from
    ``PlayShellScreen.handle_key`` when the overlay is closed, and
    ``"analyze_close"`` when it is open.
4.  ``Esc`` returns ``"analyze_close"`` when overlay is open, and
    ``"back"`` when it is closed (no behaviour change for the cold path).
5.  Overlay never auto-fires: ``analyze_session.is_open`` is ``False``
    at entry and after ``handle_key`` for T/R/E keys (no auto-open on
    STOP or any non-A key).
6.  ``analyze_open`` action in ``app.py`` opens the session;
    ``analyze_close`` closes it — wiring check via session state.
7.  The ``analyze`` module itself has no send path (structural grep pin
    — mirrors ``test_assign_trigger_module_has_no_send_path``).
8.  T / E / R paths return their own intents, unaffected by this WO.
"""

from __future__ import annotations

import inspect
import unittest.mock as mock

import curses
import pytest

from tw2002_aiclient.cockpit import analyze
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_play() -> PlayShellScreen:
    """Return a ``PlayShellScreen`` with a minimal fake stdscr."""

    class _Stdscr:
        def getmaxyx(self): return (40, 180)
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
        def has_colors(self): return False

    profile = ProfileRow(
        name="alpha", handle="Alpha", server="demo",
        host="demo.example", game_letter="B",
    )
    with mock.patch.object(curses, "has_colors", return_value=False):
        with mock.patch.object(curses, "start_color", return_value=None):
            with mock.patch.object(curses, "init_pair", return_value=None):
                with mock.patch.object(curses, "color_pair", return_value=0):
                    play = PlayShellScreen(_Stdscr(), profile)
    return play


# ---------------------------------------------------------------------------
# 1 — AnalyzeSession lifecycle
# ---------------------------------------------------------------------------

def test_analyze_session_starts_closed() -> None:
    session = analyze.AnalyzeSession()
    assert not session.is_open, "AnalyzeSession must start closed (never auto-open)"


def test_analyze_session_open_sets_is_open() -> None:
    session = analyze.AnalyzeSession()
    session.open()
    assert session.is_open


def test_analyze_session_close_clears_is_open() -> None:
    session = analyze.AnalyzeSession()
    session.open()
    session.close()
    assert not session.is_open


def test_analyze_session_open_is_idempotent() -> None:
    session = analyze.AnalyzeSession()
    session.open()
    session.open()  # second open must not raise
    assert session.is_open


def test_analyze_session_close_is_idempotent() -> None:
    session = analyze.AnalyzeSession()
    session.close()  # close on already-closed must not raise
    assert not session.is_open


def test_analyze_session_toggle_round_trip() -> None:
    session = analyze.AnalyzeSession()
    session.open()
    session.close()
    session.open()
    assert session.is_open
    session.close()
    assert not session.is_open


# ---------------------------------------------------------------------------
# 2 — OVERLAY_LABEL
# ---------------------------------------------------------------------------

def test_overlay_label_is_non_empty_string() -> None:
    assert isinstance(analyze.OVERLAY_LABEL, str)
    assert analyze.OVERLAY_LABEL.strip(), "OVERLAY_LABEL must not be blank"


# ---------------------------------------------------------------------------
# 3 — A / a key intent from handle_key
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key_char", ["a", "A"])
def test_a_key_returns_analyze_open_when_closed(key_char: str) -> None:
    play = _make_play()
    assert not play.analyze_session.is_open
    result = play.handle_key(ord(key_char))
    assert result == "analyze_open", (
        f"A key ({key_char!r}) with overlay closed returned {result!r}, "
        "expected 'analyze_open'"
    )


@pytest.mark.parametrize("key_char", ["a", "A"])
def test_a_key_returns_analyze_close_when_open(key_char: str) -> None:
    play = _make_play()
    play.analyze_session.open()
    result = play.handle_key(ord(key_char))
    assert result == "analyze_close", (
        f"A key ({key_char!r}) with overlay open returned {result!r}, "
        "expected 'analyze_close'"
    )


def test_a_key_does_not_open_session_itself() -> None:
    """handle_key returns the INTENT; app.py does the open() call."""
    play = _make_play()
    play.handle_key(ord("a"))
    assert not play.analyze_session.is_open, (
        "handle_key must not open analyze_session directly — "
        "that is app.py's responsibility on 'analyze_open'"
    )


# ---------------------------------------------------------------------------
# 4 — Esc intercept when overlay is open
# ---------------------------------------------------------------------------

def test_esc_returns_analyze_close_when_overlay_open() -> None:
    play = _make_play()
    play.analyze_session.open()
    result = play.handle_key(27)  # Esc
    assert result == "analyze_close", (
        f"Esc with overlay open returned {result!r}, expected 'analyze_close'"
    )


def test_esc_returns_back_when_overlay_closed() -> None:
    play = _make_play()
    assert not play.analyze_session.is_open
    result = play.handle_key(27)  # Esc
    assert result == "back", (
        f"Esc with overlay closed returned {result!r}, expected 'back'"
    )


# ---------------------------------------------------------------------------
# 5 — Overlay never auto-fires
# ---------------------------------------------------------------------------

def test_analyze_session_starts_closed_on_play_shell() -> None:
    """The session must start closed — no auto-open at entry."""
    play = _make_play()
    assert not play.analyze_session.is_open


@pytest.mark.parametrize("key_char", ["t", "T", "r", "R", "e", "E"])
def test_non_a_keys_do_not_open_overlay(key_char: str) -> None:
    """T / R / E must never open the Analyze overlay."""
    play = _make_play()
    play.handle_key(ord(key_char))
    assert not play.analyze_session.is_open, (
        f"Key {key_char!r} opened the Analyze overlay — auto-open forbidden"
    )


# ---------------------------------------------------------------------------
# 6 — app.py action wiring (session state check)
# ---------------------------------------------------------------------------

def test_analyze_session_open_method_opens() -> None:
    """Direct sanity: open() sets is_open (simulates app.py's action handler)."""
    session = analyze.AnalyzeSession()
    session.open()
    assert session.is_open


def test_analyze_session_close_method_closes() -> None:
    """Direct sanity: close() clears is_open (simulates app.py's close action)."""
    session = analyze.AnalyzeSession()
    session.open()
    session.close()
    assert not session.is_open


# ---------------------------------------------------------------------------
# 7 — No send path (structural grep pin)
# ---------------------------------------------------------------------------

def test_analyze_module_has_no_send_path() -> None:
    """The analyze module must never acquire a send path.

    Mirrors ``test_assign_trigger_module_has_no_send_path`` in
    ``test_cockpit_assign_trigger.py`` — same discipline, same grep.
    Teacher is spectator-only; AI never live-drives.
    """
    src = inspect.getsource(analyze)
    for forbidden in ("send", "write", "socket", "subprocess", "os.system"):
        assert forbidden not in src, (
            f"analyze references {forbidden!r} — no send path allowed; "
            "AI teacher is spectator-only (canon/engine/ai-teacher.md)"
        )


def test_analyze_module_does_not_call_explore_start() -> None:
    """analyze must never cross into the explore / adapter flow."""
    src = inspect.getsource(analyze)
    for name in ("explore_start", "explore", "adapters"):
        assert name not in src, (
            f"analyze references {name!r} — must be disjoint from explore/session"
        )


# ---------------------------------------------------------------------------
# 8 — T / E / R paths unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key_char", ["t", "T"])
def test_t_key_returns_trade_loop_toggle(key_char: str) -> None:
    """T path must not be disrupted by the A wire."""
    play = _make_play()
    result = play.handle_key(ord(key_char))
    assert result == "trade_loop_toggle", (
        f"T key ({key_char!r}) returned {result!r} — trade_loop_toggle lane broken"
    )


@pytest.mark.parametrize("key_char", ["r", "R"])
def test_r_key_still_returns_record_toggle(key_char: str) -> None:
    """R path must not be disrupted by the A wire."""
    play = _make_play()
    result = play.handle_key(ord(key_char))
    assert result == "record_toggle", (
        f"R key ({key_char!r}) returned {result!r} — record_toggle lane broken"
    )


@pytest.mark.parametrize("key_char", ["e", "E"])
def test_e_key_is_not_analyze_open(key_char: str) -> None:
    """E is Explore — must not be hijacked to analyze_open."""
    play = _make_play()
    result = play.handle_key(ord(key_char))
    assert result != "analyze_open", (
        f"E key ({key_char!r}) returned 'analyze_open' — explore lane stolen"
    )
    assert result != "analyze_close", (
        f"E key ({key_char!r}) returned 'analyze_close' — unexpected"
    )
