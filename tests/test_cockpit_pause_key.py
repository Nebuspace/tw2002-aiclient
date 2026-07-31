"""`Space` pause -- the cockpit-level wire (WO-AUTOLOOP-RELAUNCH-COCKPIT).

Mirrors ``tests/test_cockpit_panic.py``'s "cockpit wire" section: proves
the key resolves to the pause intent through the REAL
``PlayShellScreen.handle_key``, and proves it raises no confirm gate --
the same load-bearing asymmetry panic pins, now shared by pause (both are
halt-direction, so neither spends, so neither gates).
"""

from __future__ import annotations

import curses
from unittest import mock

import pytest

from tw2002_aiclient.cockpit import autoloop_controls
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow


def _make_play() -> PlayShellScreen:
    """Mirrors ``tests/test_cockpit_panic.py``'s own helper."""

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
                    return PlayShellScreen(_Stdscr(), profile)


def test_play_shell_returns_the_pause_intent():
    assert _make_play().handle_key(ord(" ")) == autoloop_controls.PAUSE_INTENT


def test_pause_key_raises_no_confirm_gate():
    """One key, one read -- same discipline `test_cockpit_panic.py`'s own
    version of this test uses, to avoid the 'gate raised then cleared'
    vacuity trap."""
    play = _make_play()
    assert play._arm_confirm is None
    play.handle_key(ord(" "))
    assert play._arm_confirm is None, "pause raised a confirm gate"


def test_pause_does_not_shadow_port_trade_or_the_teach_keys():
    """`p` is no longer bound to `panic` on this calm path (hub REVISE
    2026-07-31) -- it flips the local `port_trade_on` toggle instead. See
    `tests/test_play_strip_trainer_toggles.py` for the dedicated pins."""
    play = _make_play()
    before = play.port_trade_on
    assert play.handle_key(ord("p")) is None
    assert play.port_trade_on is (not before)
    assert play.handle_key(ord("a")) == "analyze_open"
    assert play.handle_key(ord("t")) == "assign_trigger"
    assert play.handle_key(ord("r")) == "record_toggle"


def test_panic_and_teach_keys_do_not_shadow_pause():
    play = _make_play()
    assert play.handle_key(ord(" ")) == autoloop_controls.PAUSE_INTENT


def test_confirm_gate_intercepts_pause_while_up():
    """The gate's total capture (WO-P5-063's own ordering contract) covers
    the new pause key too -- a `y/N` prompt for something else must not
    let Space slip through underneath it."""
    play = _make_play()
    play.begin_arm_confirm("Explore", cycles=5)
    assert play.handle_key(ord(" ")) is None, "pause fired through an open confirm gate"
    assert play._arm_confirm is None  # single-shot: the gate is gone either way


def test_pause_fires_with_no_run_armed():
    """No precondition, deliberately -- same reasoning `panic.py` states for
    its own key."""
    play = _make_play()
    assert getattr(play, "_arm_confirm", None) is None
    assert play.handle_key(ord(" ")) == autoloop_controls.PAUSE_INTENT
