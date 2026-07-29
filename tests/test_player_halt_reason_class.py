"""WO-PLAYER-HALT-NEVER-AUTO-CLASS -- the qualified halt reason `code:detail`.

The player's `never_auto_action` was honest only while
`NEVER_AUTO_ACTION_CLASSES` had exactly one member. That set is explicitly
designed to grow ("a class added there is refused here the same day"), so the
bare reason was a latent copy of the explore defect #213 fixed.

# What this file owns, and what it deliberately does not

The `_gate` behaviour itself is already pinned where it lives:
`tests/test_never_auto_action.py` owns the money_prompt refusal, and
`tests/test_loop_player.py::test_widening_canons_set_widens_the_players_refusal`
owns the SECOND class (`port_trade`) that proves the class is read from the
observation rather than being a constant. Re-asserting either here would be a
second layer agreeing with the first -- unreachable coverage that looks like
diligence.

This file owns the parts that are NEW: the code/detail split, the validation
that accepts a qualified reason without exploding the closed vocabulary, and
the banner's resolution of it.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import stopbanner as sb
from tw2002_aiclient.loops import player as p


def _halted(reason):
    return p.ReplayResult(
        outcome="halted", loop_name="L", steps=(), sends_issued=0,
        reason=reason, halted_at=0,
    )


# --------------------------------------------------------------------------
# The code/detail split
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "reason,expected",
    [
        ("never_auto_action:money_prompt", "never_auto_action"),
        ("never_auto_action:port_trade", "never_auto_action"),
        ("operator_stop", "operator_stop"),
        # A detail containing the separator must not truncate the detail's
        # own content out of existence -- split on the FIRST separator only.
        ("never_auto_action:a:b", "never_auto_action"),
        (None, None),
        ("", None),
        (123, None),
    ],
)
def test_halt_reason_code_returns_the_bare_code(reason, expected) -> None:
    assert p.halt_reason_code(reason) == expected


# --------------------------------------------------------------------------
# Validation accepts the qualified form WITHOUT opening the vocabulary
# --------------------------------------------------------------------------

def test_a_qualified_reason_is_accepted() -> None:
    assert _halted("never_auto_action:money_prompt").reason == "never_auto_action:money_prompt"


def test_an_unqualified_reason_is_still_accepted() -> None:
    """The old shape must keep working -- most halts have no class to name."""
    assert _halted("operator_stop").reason == "operator_stop"


@pytest.mark.parametrize("bogus", ["totally_made_up", "totally_made_up:money_prompt"])
def test_an_unknown_code_is_still_refused_qualified_or_not(bogus) -> None:
    """The closed vocabulary is still closed.

    Without this, "accept anything with a colon in it" would satisfy the
    accept-the-qualified-form requirement and quietly delete the guard.
    """
    with pytest.raises(ValueError):
        _halted(bogus)


def test_the_closed_vocabulary_was_not_exploded_into_class_pairs() -> None:
    """`HALT_REASONS` stays a readable set of CODES.

    Enumerating code x class would make it grow silently every time
    `classify` gains a class, and `test_loop_player`'s
    `reported == HALT_REASONS` pin would stop being something a human can
    read and check.
    """
    assert not [r for r in p.HALT_REASONS if p.QUALIFIER_SEP in r]


# --------------------------------------------------------------------------
# The banner resolves the qualified form -- additively
# --------------------------------------------------------------------------

def test_the_banner_labels_a_qualified_reason_by_its_code() -> None:
    out = sb.intervention_reason_label("never_auto_action:money_prompt")
    assert out.startswith("never auto action"), out
    assert "money_prompt" in out, out
    assert out != "never_auto_action:money_prompt", "the code went out raw"


def test_the_banner_still_labels_an_unqualified_reason_exactly_as_before() -> None:
    assert sb.intervention_reason_label("never_auto_action") == "never auto action"
    assert sb.intervention_reason_label("unrecognized_screen") == "unrecognized screen"


@pytest.mark.parametrize("code", ["made_up_code", "made_up_code:detail", "a:b:c"])
def test_an_unknown_code_still_passes_through_as_its_own_text(code) -> None:
    """Open-by-construction, unchanged.

    A qualified code whose BASE is unknown must not be labelled from a
    neighbouring entry -- that is the "never a guessed label" rule the
    resolver's docstring sets, and the new split must not weaken it.
    """
    assert sb.intervention_reason_label(code) == code


@pytest.mark.parametrize("code", [None, ""])
def test_empty_and_none_still_render_the_unknown_glyph(code) -> None:
    assert sb.intervention_reason_label(code) == sb.UNKNOWN_REASON


def test_the_catalog_grew_no_per_class_rows() -> None:
    """Accept 3: label by base code, do not add a row per class.

    A catalog with `never_auto_action:money_prompt` in it would pass every
    rendering test above while reintroducing exactly the combinatorial
    growth this design avoids.
    """
    assert not [k for k in sb.INTERVENTION_REASON_LABELS if ":" in k]


def test_the_two_separator_constants_agree() -> None:
    """`stopbanner` declares its own separator rather than importing the
    loop engine's -- a deliberate copy to keep the cockpit's "plain strings
    only" contract. A copy needs a pin, or it is just a hope.
    """
    assert sb._QUALIFIER_SEP == p.QUALIFIER_SEP


# --------------------------------------------------------------------------
# The unknown path is untouched (Accept 5)
# --------------------------------------------------------------------------

def test_an_unknown_screen_still_halts_bare_and_unqualified() -> None:
    """`unknown` has no class worth naming -- qualifying it would be the
    #213 lie in the opposite direction."""
    halt = p._gate(p._Observation(klass="unknown"))
    assert halt == p.HALT_UNRECOGNIZED_SCREEN
    assert p.QUALIFIER_SEP not in halt


def test_the_player_did_not_grow_explores_not_drivable_vocabulary() -> None:
    """Accept 5. The player only auto-drives taught macros, so
    "recognised but not drivable" is not a state it has -- a screen it does
    not recognise escalates, and everything else is simply driven. Importing
    explore's vocabulary here would describe a situation this loop cannot be
    in.
    """
    assert not hasattr(p, "HALT_NOT_DRIVABLE")
    for klass in ("sector_display", "fighter_encounter"):
        assert p._gate(p._Observation(klass=klass)) is None, klass
