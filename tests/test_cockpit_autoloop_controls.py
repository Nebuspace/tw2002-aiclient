"""``cockpit/autoloop_controls.py`` -- pause key + relaunch offer key +
relaunch confirm label (WO-AUTOLOOP-RELAUNCH-COCKPIT).

Mirrors ``tests/test_cockpit_panic.py``'s composer-level structure: key
resolution, hardening, and the money-path label's MEANING (not just field
presence).
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import autoloop_controls, panic


# --------------------------------------------------------------------------
# Pause key -- ungated, mirrors panic's own resolver
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord(" ")])
def test_pause_key_resolves(key):
    assert autoloop_controls.resolve_pause_key(key) is True


@pytest.mark.parametrize(
    "key", [ord("p"), ord("q"), ord("g"), ord("G"), 27, 10, -1, 0]
)
def test_other_keys_do_not_fire_pause(key):
    assert autoloop_controls.resolve_pause_key(key) is False


def test_bool_does_not_fire_pause():
    """``isinstance(True, int)`` holds and ``True == 1`` -- an unrejected
    bool would make ``chr(1)`` fire the pause, same hazard
    ``panic.resolve_panic_key`` guards against."""
    assert autoloop_controls.resolve_pause_key(True) is False
    assert autoloop_controls.resolve_pause_key(False) is False


@pytest.mark.parametrize("hostile", [None, " ", b" ", 3.5, object(), [], {}])
def test_hostile_input_never_raises_and_never_fires_pause(hostile):
    assert autoloop_controls.resolve_pause_key(hostile) is False


def test_pause_intent_is_distinct_from_panic_and_arm_confirm():
    """The app loop routes on this string; it must never collide with an
    intent that carries different (or no) confirm-gate semantics."""
    from tw2002_aiclient.cockpit import armconfirm

    assert autoloop_controls.PAUSE_INTENT == "pause"
    assert autoloop_controls.PAUSE_INTENT != panic.PANIC_INTENT
    assert autoloop_controls.PAUSE_INTENT not in (armconfirm.CONFIRM, armconfirm.CANCEL)


# --------------------------------------------------------------------------
# Relaunch offer key -- G/g, checked in the play loop (like explore's E/e)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [ord("g"), ord("G")])
def test_relaunch_offer_key_resolves(key):
    assert autoloop_controls.resolve_relaunch_offer_key(key) is True


@pytest.mark.parametrize(
    "key",
    [ord("l"), ord("L"), ord("e"), ord("E"), ord("r"), ord("p"), 27, 10, -1, 0],
)
def test_other_keys_do_not_offer_relaunch(key):
    """`L`/`l` in particular: canon reserves `L)chains` for the unbuilt
    Trade-Loop-Chains popup -- this module must not steal it."""
    assert autoloop_controls.resolve_relaunch_offer_key(key) is False


def test_bool_does_not_offer_relaunch():
    assert autoloop_controls.resolve_relaunch_offer_key(True) is False
    assert autoloop_controls.resolve_relaunch_offer_key(False) is False


@pytest.mark.parametrize("hostile", [None, "g", b"g", 3.5, object(), [], {}])
def test_hostile_input_never_raises_and_never_offers_relaunch(hostile):
    assert autoloop_controls.resolve_relaunch_offer_key(hostile) is False


# --------------------------------------------------------------------------
# The relaunch confirm label -- meaning, not raw field names
# --------------------------------------------------------------------------

def test_label_states_replay_from_start():
    label = autoloop_controls.compose_relaunch_confirm_action(5)
    assert "replays from the beginning" in label


def test_label_discloses_a_genuine_send_count():
    label = autoloop_controls.compose_relaunch_confirm_action(12)
    assert "12 sends already issued" in label


def test_label_renders_unknown_as_question_mark_not_zero():
    """`sends_already_issued=None` is "unknown", never "0" -- the same rule
    `adapters.autoloop_relaunch`'s own docstring states for the wire
    field this label renders."""
    label = autoloop_controls.compose_relaunch_confirm_action(None)
    assert "? sends already issued" in label
    assert "0 sends already issued" not in label


@pytest.mark.parametrize("hostile", [-1, "5", 5.0, True, False, object(), []])
def test_hostile_or_negative_send_counts_render_as_unknown(hostile):
    """A negative count, a non-int, or a bool is not a number this label
    can prove -- degrades to the same honest `?` as `None`, never a
    fabricated figure."""
    label = autoloop_controls.compose_relaunch_confirm_action(hostile)
    assert "? sends already issued" in label


def test_label_never_says_the_word_resume():
    """Hub ruling 2026-07-27 (1)+(3): `resume` stays refused everywhere in
    cockpit affordances, including this money-path label."""
    for value in (0, 12, None, -1, "x"):
        label = autoloop_controls.compose_relaunch_confirm_action(value)
        assert "resume" not in label.lower()


def test_label_never_raises_on_any_input():
    for hostile in (None, "x", b"x", 3.5, object(), [], {}, True, False, -1):
        autoloop_controls.compose_relaunch_confirm_action(hostile)  # must not raise


# --------------------------------------------------------------------------
# No "resume" anywhere in this module's own vocabulary
# --------------------------------------------------------------------------

def test_module_exposes_no_resume_named_attribute():
    names = [n for n in vars(autoloop_controls) if not n.startswith("_")]
    for name in names:
        assert "resume" not in name.lower(), f"module exposes a resume-named attribute: {name}"


def test_module_constants_never_spell_resume():
    for name in ("PAUSE_INTENT", "RELAUNCH_ACTION_LABEL"):
        value = getattr(autoloop_controls, name)
        assert "resume" not in value.lower()
