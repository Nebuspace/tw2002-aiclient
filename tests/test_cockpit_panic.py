"""The panic control (WO-P5-071).

The central pin here is a *negative* one: panic must NOT be confirm-gated.
Every other affordance in the N5 cluster is, so "make it consistent with
`armconfirm`" is a plausible-sounding change that would be a safety
regression -- adding a keystroke to the emergency path to satisfy a rule
written to protect the commitment path. That asymmetry is pinned
mechanically rather than left to a docstring nobody re-reads.
"""

from __future__ import annotations

import inspect

import pytest

from tw2002_aiclient.cockpit import armconfirm, panic, teachband


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
    `mode-line-and-teach-controls.md:234` claims a uniform `KEY)verb` shape,
    but the band literal it prints is `P panic`, identically at `:136`,
    `:219` and `visual-language.md:302`. Conflict reported to the hub;
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


def test_panic_wears_chrome_not_danger():
    """`danger` is canon's tone for a prompt about to spend live turns
    (`armconfirm.ARM_CONFIRM_TONE`). Panic spends nothing, and a
    permanently-red token in the calm band would dilute the one place red
    means 'this commits'."""
    assert panic.PANIC_TONE == "chrome"
    assert panic.PANIC_TONE != armconfirm.ARM_CONFIRM_TONE
