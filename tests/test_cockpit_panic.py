"""The panic control (WO-P5-071).

The central pin here is a *negative* one: panic must NOT be confirm-gated.
Every other affordance in the N5 cluster is, so "make it consistent with
`armconfirm`" is a plausible-sounding change that would be a safety
regression -- adding a keystroke to the emergency path to satisfy a rule
written to protect the commitment path. That asymmetry is pinned
mechanically rather than left to a docstring nobody re-reads.
"""

from __future__ import annotations

import curses
import inspect
from unittest import mock

import pytest

from tw2002_aiclient.cockpit import armconfirm, panic, teachband
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow


def _make_play() -> PlayShellScreen:
    """A ``PlayShellScreen`` with a minimal fake stdscr (mirrors
    ``tests/test_cockpit_analyze.py``'s helper)."""

    class _Stdscr:
        def getmaxyx(self): return (40, 160)
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
# Key binding
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord("p"), ord("P")])
def test_both_cases_bind(key):
    """Matches the A/R/T teach keys' posture -- `screens.py` binds both
    cases for each of them."""
    assert panic.resolve_panic_key(key) is True


@pytest.mark.parametrize("key", [ord("q"), ord("a"), ord("r"), ord("t"), 27, 10, -1, 0])
def test_other_keys_do_not_fire_panic(key):
    assert panic.resolve_panic_key(key) is False


def test_bool_does_not_fire_panic():
    """`isinstance(True, int)` holds and `True == 1`, so an unrejected bool
    would make `chr(1)` fire the halt control."""
    assert panic.resolve_panic_key(True) is False
    assert panic.resolve_panic_key(False) is False


@pytest.mark.parametrize("hostile", [None, "p", b"p", 3.5, object(), [], {}])
def test_hostile_input_never_raises_and_never_fires(hostile):
    assert panic.resolve_panic_key(hostile) is False


# --------------------------------------------------------------------------
# The load-bearing asymmetry: panic is NOT confirm-gated
# --------------------------------------------------------------------------

def test_panic_module_has_no_confirm_step():
    """Structural, not textual: nothing in this module may expose a confirm
    resolver, and it must not import the confirm gate at all.

    Written as an attribute/namespace check rather than a grep of the
    source, because a grep would hit the docstring -- which *discusses*
    confirm gating at length and would keep any such pin permanently, and
    misleadingly, green.
    """
    names = [n for n in vars(panic) if not n.startswith("_")]
    for name in names:
        assert "confirm" not in name.lower(), f"panic exposes a confirm step: {name}"
    assert not hasattr(panic, "resolve_arm_confirm_key")
    imported = {v for v in vars(panic).values() if inspect.ismodule(v)}
    assert armconfirm not in imported, "panic must not reach the confirm gate"


def test_panic_intent_is_distinct_from_every_arm_intent():
    """The app loop routes on this string. If panic shared a verb with an
    arm/launch intent it would inherit that path's confirm gate by
    accident -- the exact regression this WO is guarding."""
    assert panic.PANIC_INTENT == "panic"
    assert panic.PANIC_INTENT not in (armconfirm.CONFIRM, armconfirm.CANCEL)


def test_arming_is_still_confirm_gated():
    """The other half of the asymmetry -- proves the pin above is about
    *direction*, not about confirm gates being unwanted generally.

    If someone 'simplified' by removing the arm gate too, this goes red
    while the panic pins stay green, which is the correct signal.
    """
    assert armconfirm.resolve_arm_confirm_key(ord("y")) == armconfirm.CONFIRM
    assert armconfirm.resolve_arm_confirm_key(ord("\n")) == armconfirm.CANCEL
    assert armconfirm.resolve_arm_confirm_key(ord("n")) == armconfirm.CANCEL


# --------------------------------------------------------------------------
# The band token
# --------------------------------------------------------------------------

def test_panic_token_is_canon_literal_spelling():
    """`P panic` -- a SPACE, not `P)anic`. Canon's prose at
    `mode-line-and-teach-controls.md:235` claims a uniform `KEY)verb` shape,
    but the band literal it prints is `P panic`, identically at `:136`,
    `:220` and `visual-language.md:306`. Conflict reported to the hub;
    the thrice-repeated cross-file literal is what ships."""
    assert panic.PANIC_TOKEN == "P panic"


def test_band_carries_panic_last():
    """Canon's band order puts panic at the tail."""
    band = teachband.compose_teach_band()
    assert band.endswith(panic.PANIC_TOKEN)
    assert band == "A)nalyze  R)ecord  T)rigger  P panic"


def test_band_and_module_cannot_disagree_about_the_spelling():
    """`teachband` imports the token rather than re-spelling it. Pinned so a
    future 'tidy-up' that inlines the string reintroduces the drift hazard
    the `T)rigger`/`T)assign` split already demonstrated on this surface."""
    assert panic.PANIC_TOKEN in teachband.TEACH_TOKENS


def test_panic_token_is_ascii():
    """`visual-language.md`: band tokens have no unicode twin."""
    assert panic.PANIC_TOKEN.isascii()


# --------------------------------------------------------------------------
# The cockpit wire -- key reaches the intent, and reaches it UNGATED
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord("p"), ord("P")])
def test_play_shell_returns_the_panic_intent(key):
    assert _make_play().handle_key(key) == panic.PANIC_INTENT


def test_panic_key_raises_no_confirm_gate():
    """The wire-level half of the no-confirm pin.

    Read `_arm_confirm` immediately after the single keypress, with nothing
    else driving the screen -- an earlier WO on this surface shipped a pin
    that inspected the gate *after* a loop had already cleared it, which
    made 'gate raised then dismissed' and 'gate never raised' look
    identical. One key, one read.
    """
    play = _make_play()
    assert play._arm_confirm is None
    play.handle_key(ord("P"))
    assert play._arm_confirm is None, "panic raised a confirm gate — see cockpit/panic.py"


def test_panic_does_not_shadow_the_teach_keys():
    """`P` sits after A/R/T in the handler; none of them may change meaning."""
    play = _make_play()
    assert play.handle_key(ord("a")) == "analyze_open"
    assert play.handle_key(ord("t")) == "assign_trigger"
    assert play.handle_key(ord("r")) == "record_toggle"


def test_panic_fires_with_no_run_armed():
    """No 'is a run armed?' precondition, deliberately: a panic that refuses
    because the cockpit believes nothing is running fails exactly when the
    cockpit's belief is the thing that is wrong. The daemon verb is
    idempotent, so an unnecessary press is free."""
    play = _make_play()
    assert getattr(play, "_arm_confirm", None) is None
    assert play.handle_key(ord("p")) == panic.PANIC_INTENT


def test_panic_wears_chrome_not_danger():
    """`danger` is canon's tone for a prompt about to spend live turns
    (`armconfirm.ARM_CONFIRM_TONE`). Panic spends nothing, and a
    permanently-red token in the calm band would dilute the one place red
    means 'this commits'."""
    assert panic.PANIC_TONE == "chrome"
    assert panic.PANIC_TONE != armconfirm.ARM_CONFIRM_TONE
