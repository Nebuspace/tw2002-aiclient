"""`P`/`C`/`S` -- the trainer calm band's own local chrome toggles
(WO-PLAY-STRIP-TRAINER-CHROME, hub REVISE 2026-07-31).

The band (`cockpit/teachband.py::compose_teach_band`) advertises
``P)ort Trade``, ``C)argo Hold Upgrade``, ``S)hip Upgrade`` with a caller-
supplied ``·ON``/``·OFF`` suffix. The STATUS-DONE cut of this WO composed
that suffix from three real ``PlayShellScreen`` booleans but bound no key
to flip any of them -- worse, ``P`` was still silently wired to the OLD
``cockpit.panic`` halt control underneath the NEW label, a
plausible-but-wrong claim caught in hub REVISE
(``tests/test_cockpit_panic.py``'s own "cockpit wire" section pins the
retirement of that old wire).

This file pins the NEW wire: each key flips only its own boolean, returns
no intent (there is no daemon-side spend gate to wire yet --
WO-PLAY-STRIP-POLICY-AUTO owns that follow-on), raises no confirm gate,
and does not shadow (or get shadowed by) any neighboring key.
"""

from __future__ import annotations

import curses
from unittest import mock

import pytest

from tw2002_aiclient.screens import PlayShellScreen, ProfileRow


def _make_play() -> PlayShellScreen:
    """Mirrors ``tests/test_cockpit_panic.py``'s own helper -- a real
    ``__init__`` run (not ``object.__new__``) so the three toggle
    booleans this file exercises are genuinely set to their DECISION
    defaults, not left unset."""

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


# --------------------------------------------------------------------------
# Defaults -- DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 2
# --------------------------------------------------------------------------

def test_all_three_toggles_default_on():
    play = _make_play()
    assert play.port_trade_on is True
    assert play.cargo_upgrade_on is True
    assert play.ship_upgrade_on is True


# --------------------------------------------------------------------------
# Each key flips only its own boolean, both cases bind, returns no intent
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord("p"), ord("P")])
def test_p_toggles_port_trade_only(key):
    play = _make_play()
    assert play.handle_key(key) is None
    assert play.port_trade_on is False
    assert play.cargo_upgrade_on is True
    assert play.ship_upgrade_on is True


@pytest.mark.parametrize("key", [ord("c"), ord("C")])
def test_c_toggles_cargo_upgrade_only(key):
    play = _make_play()
    assert play.handle_key(key) is None
    assert play.cargo_upgrade_on is False
    assert play.port_trade_on is True
    assert play.ship_upgrade_on is True


@pytest.mark.parametrize("key", [ord("s"), ord("S")])
def test_s_toggles_ship_upgrade_only(key):
    play = _make_play()
    assert play.handle_key(key) is None
    assert play.ship_upgrade_on is False
    assert play.port_trade_on is True
    assert play.cargo_upgrade_on is True


def test_second_press_flips_back():
    play = _make_play()
    play.handle_key(ord("p"))
    assert play.port_trade_on is False
    play.handle_key(ord("P"))
    assert play.port_trade_on is True


# --------------------------------------------------------------------------
# No confirm gate -- these spend nothing, they are display-only chrome
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord("p"), ord("c"), ord("s")])
def test_toggle_keys_raise_no_confirm_gate(key):
    play = _make_play()
    assert play._arm_confirm is None
    play.handle_key(key)
    assert play._arm_confirm is None, f"{chr(key)!r} raised a confirm gate"


def test_confirm_gate_intercepts_toggle_keys_while_up():
    """The gate's total capture (WO-P5-063) covers P/C/S too -- a `y/N`
    prompt for something else must not let a toggle key slip through and
    silently flip local chrome state underneath it."""
    play = _make_play()
    play.begin_arm_confirm("Explore", cycles=5)
    before = play.port_trade_on
    assert play.handle_key(ord("p")) is None, "toggle fired through an open confirm gate"
    assert play.port_trade_on == before, "toggle state changed while the confirm gate was up"


# --------------------------------------------------------------------------
# No shadowing either direction
# --------------------------------------------------------------------------

def test_toggle_keys_do_not_shadow_the_teach_keys():
    play = _make_play()
    assert play.handle_key(ord("a")) == "analyze_open"
    assert play.handle_key(ord("t")) == "trade_loop_toggle"
    assert play.handle_key(ord("r")) == "record_toggle"


def test_teach_keys_do_not_shadow_the_toggle_keys():
    play = _make_play()
    play.handle_key(ord("a"))  # opens the analyze overlay -- unrelated state
    assert play.handle_key(ord("p")) is None
    assert play.port_trade_on is False


# --------------------------------------------------------------------------
# `P` is retired from panic -- the negative half of the same pin, from this
# file's own vantage point (the composer-level pin lives in
# tests/test_cockpit_panic.py).
# --------------------------------------------------------------------------

def test_p_no_longer_returns_the_panic_intent():
    from tw2002_aiclient.cockpit import panic

    play = _make_play()
    assert play.handle_key(ord("P")) != panic.PANIC_INTENT
