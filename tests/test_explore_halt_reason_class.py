"""WO-EXPLORE-HALT-REASON-CLASS -- explore halt reasons must carry the class.

# The defect, reproduced from real wire

`_gate_screen` collapsed every non-movement class into `unrecognized_screen`.
On the live fighter cells in `dock-kernel-live-20260729T0407Z`, `classify`
returned `fighter_encounter` for the very same bytes the halt reason called
unrecognized. That is not merely imprecise -- it points a reader at the wrong
repair, inviting them to go write a classifier that already exists. It is the
same shape as `dock_screen_unrecognized` standing for two different failures,
which cost the dock WO a full diagnosis cycle.

# What is pinned, and why BOTH directions

The trap in a rename like this is a reason string that *looks* honest while
the caller still cannot tell the cases apart. So the contract is pinned in
both directions:

  * a RECOGNISED class must never produce bare `unrecognized_screen`
  * a genuine `unknown` must never produce a class-qualified reason

One direction alone is satisfiable by a mutation that relabels everything --
which is the defect wearing new vocabulary.

Halt *behaviour* is explicitly unchanged, and that is pinned separately:
whether a screen halts is still decided by class membership, not by the
reason string.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient.loops.player import OUTCOME_HALTED
from tw2002_aiclient.session import sector_explore as sx
from tw2002_aiclient.session.classify import NEVER_AUTO_ACTION_CLASSES, classify_screen
from tw2002_aiclient.session.control_lock import ControlLock

from .conftest import FakeAttachSession

WORLD = "w-halt-reason"

MOVEMENT = "Command [TL=00:00:00]:[42] (?=Help)? : "
MONEY = "How many holds of Fuel Ore do you want? [50]? "
# Real captured wire -- the letter tuple IS the anchor's specificity, so a
# hand-written `Option? [R]` does NOT classify as a fighter encounter. Written
# out rather than read from `.samantha/audit/` because that tree is gitignored:
# a fixture sourced from it would silently vanish in a worktree or in CI.
FIGHTER = (
    "Sector  : 14410 in uncharted space.\n"
    "Fighters: 1 (belong to a trader) [Defensive]\n"
    "You have to destroy the fighters to remain in this sector.\n"
    "Your fighters: 242 vs. theirs: 1\n"
    "Option? (A,D,I,R,S,?):?"
)
FIGHTER_PROMPT = "Option? (A,D,I,R,S,?):?"
UNKNOWN = "<StarDock> Where to? (?=Help)"
# A SECOND recognised-but-not-drivable class. Its whole job is to be a
# different class from `fighter_encounter` through the same branch -- see
# `test_a_qualified_reason_names_exactly_the_class_that_produced_it`.
SECTOR_DISPLAY = (
    "Sector  : 42 in uncharted space.\n"
    "Ports   : Somewhere, Class 3 (SBB)\n"
    "Warps to Sector(s) :  (1) - 2\n"
)
SECTOR_DISPLAY_PROMPT = "Warps to Sector(s) :  (1) - 2"


def test_the_captured_fighter_wire_really_is_a_fighter_encounter() -> None:
    """Non-vacuity control for every fighter assertion below.

    If this fixture stopped matching the anchor it would classify `unknown`,
    and the "recognised class" tests would then be pinning the unknown path
    while still passing. Measured risk, not hypothetical: the first draft of
    this fixture said `Option? [R]` and classified `sector_display`.
    """
    assert classify_screen(FIGHTER, FIGHTER_PROMPT) == "fighter_encounter"


# --------------------------------------------------------------------------
# Direction 1 -- a recognised class must never be called unrecognized
# --------------------------------------------------------------------------

def test_a_recognised_class_halts_with_its_class_named() -> None:
    halt, klass = sx._gate_screen(FIGHTER, FIGHTER_PROMPT)
    assert klass == "fighter_encounter"
    assert halt == "halt_not_drivable:fighter_encounter", halt
    assert sx.HALT_UNRECOGNIZED_SCREEN not in halt, (
        "the screen was recognised; saying otherwise sends a reader hunting "
        "for a classifier that already exists"
    )


def test_a_never_auto_class_carries_its_class_too() -> None:
    halt, klass = sx._gate_screen(MONEY, MONEY)
    assert klass in NEVER_AUTO_ACTION_CLASSES
    assert halt == "never_auto_action:money_prompt", halt


@pytest.mark.parametrize("text,prompt", [(FIGHTER, FIGHTER_PROMPT), (MONEY, MONEY)])
def test_no_recognised_class_ever_yields_the_bare_unknown_reason(text, prompt) -> None:
    halt, klass = sx._gate_screen(text, prompt)
    assert klass != sx.CLASS_UNKNOWN
    assert halt != sx.HALT_UNRECOGNIZED_SCREEN


# --------------------------------------------------------------------------
# Direction 2 -- a genuine unknown must stay honestly unknown
# --------------------------------------------------------------------------

def test_a_genuine_unknown_still_halts_as_unrecognized() -> None:
    """Accept 2: do not invent classes. Without this, a mutation that
    qualifies EVERY reason would satisfy direction 1 and still be the same
    defect wearing new vocabulary."""
    halt, klass = sx._gate_screen(UNKNOWN, UNKNOWN)
    assert klass == sx.CLASS_UNKNOWN
    assert halt == sx.HALT_UNRECOGNIZED_SCREEN, halt
    assert ":" not in halt, "an unknown screen has no class to name"


def test_the_unknown_sentinel_is_what_classify_actually_returns() -> None:
    """`CLASS_UNKNOWN` is a copy of classify's sentinel, and a copy can drift.

    If it drifted, real unknowns would route down the named-class branch and
    emit `halt_not_drivable:unknown` -- the lie restored in the opposite
    direction, with every test above still green.
    """
    assert classify_screen("zzz qqq", "zzz qqq") == sx.CLASS_UNKNOWN


# --------------------------------------------------------------------------
# Behaviour is unchanged -- only the vocabulary moved
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,prompt,should_halt",
    [
        (MOVEMENT, MOVEMENT, False),
        (FIGHTER, FIGHTER_PROMPT, True),
        (MONEY, MONEY, True),
        (UNKNOWN, UNKNOWN, True),
    ],
)
def test_whether_we_halt_is_still_decided_by_class_not_by_the_reason(
    text, prompt, should_halt
) -> None:
    """Accept 4. The rename must not have quietly changed who stops."""
    halt, klass = sx._gate_screen(text, prompt)
    assert (halt is not None) is should_halt, (halt, klass)
    assert (klass == sx.MOVEMENT_SCREEN_CLASS) is (not should_halt)


def test_a_qualified_reason_names_exactly_the_class_that_produced_it() -> None:
    """The reason must be *derivable from* the class, not merely decorated
    with a plausible-looking one.

    TWO different classes go through the not-drivable branch, deliberately.
    With only `fighter_encounter` there, a mutation hardcoding the literal
    `"fighter_encounter"` into that branch stayed GREEN -- the single case
    could not tell "the real class" from "a constant that happens to equal
    it". Measured, not theorised: that mutation is in the matrix for this WO
    and it passed until `SECTOR_DISPLAY` was added here.
    """
    cases = (
        (FIGHTER, FIGHTER_PROMPT, "fighter_encounter"),
        (SECTOR_DISPLAY, SECTOR_DISPLAY_PROMPT, "sector_display"),
        (MONEY, MONEY, "money_prompt"),
    )
    seen = set()
    for text, prompt, expected in cases:
        halt, klass = sx._gate_screen(text, prompt)
        assert klass == expected, (klass, expected)
        assert halt.split(":")[-1] == klass, (halt, klass)
        seen.add(klass)
    assert len(seen) == 3, "the cases must not collapse to one class"


def test_two_distinct_classes_share_the_not_drivable_branch() -> None:
    """Guards the guard above: if these two ever classified the same, the
    derivability test would silently go back to being single-case."""
    _h1, k1 = sx._gate_screen(FIGHTER, FIGHTER_PROMPT)
    _h2, k2 = sx._gate_screen(SECTOR_DISPLAY, SECTOR_DISPLAY_PROMPT)
    assert k1 != k2, (k1, k2)
    assert _h1.startswith(sx.HALT_NOT_DRIVABLE) and _h2.startswith(sx.HALT_NOT_DRIVABLE)


# --------------------------------------------------------------------------
# The twin site -- recognised screen, unreadable sector number
# --------------------------------------------------------------------------

class _UnreadableSectorSession(FakeAttachSession):
    """A `main_command` screen whose sector field cannot be parsed.

    This is the only way to reach the twin site: `_gate_screen` must PASS
    (so the screen is recognised) and `read_current_sector` must then fail.
    """

    def __init__(self) -> None:
        super().__init__(initial_screen="Command [TL=00:00:00]:[] (?=Help)? : ")
        self.rx_count = 1
        self.last_rx = -10.0


def test_the_twin_site_is_genuinely_reachable() -> None:
    """Control for the test below.

    A branch that cannot be reached would let its reason say anything at all
    while the suite stayed green -- and the sibling pin in
    `test_explore_dock_new_port.py` documents a dock guard that IS
    unreachable, so this is a live distinction in this file, not a
    theoretical one.
    """
    screen = "Command [TL=00:00:00]:[] (?=Help)? : "
    halt, klass = sx._gate_screen(screen, screen)
    assert halt is None, "the gate must PASS for the twin site to be reached"
    assert klass == sx.MOVEMENT_SCREEN_CLASS


def test_an_unreadable_sector_is_not_reported_as_an_unrecognized_screen(tmp_path) -> None:
    """The second lie this WO fixes.

    `_gate_screen` has just recognised the screen as `main_command`; what
    failed is reading a sector NUMBER out of it. Reporting
    `unrecognized_screen` sent a reader after a missing classifier when the
    fault is in `read_current_sector`. `current_sector_unreadable` is not
    invented here -- `loops/player.py` already defines it for exactly this
    failure and the STOP banner already renders it.
    """
    runner = sx.ExploreRunner(
        _UnreadableSectorSession(), ControlLock(),
        state_dir=tmp_path, timeout_s=2.0, debounce_ms=1,
    )
    runner.start(WORLD, min_sectors=1, turn_budget=3)
    report = runner.stop(join_timeout=10.0).report

    assert report.outcome == OUTCOME_HALTED
    assert report.reason == "current_sector_unreadable", report.reason
    assert report.reason != sx.HALT_UNRECOGNIZED_SCREEN


# --------------------------------------------------------------------------
# Vocabulary hygiene
# --------------------------------------------------------------------------

def test_the_qualifier_separator_is_one_shape_everywhere() -> None:
    """Both branches build the reason through one helper, so a live-evidence
    reader has a single thing to split on."""
    assert sx._qualify("base", "klass") == "base:klass"


def test_not_drivable_is_distinct_from_unrecognized() -> None:
    """Two different facts need two different words. If these ever collapsed
    to the same string the WO would be undone with every other test green."""
    assert sx.HALT_NOT_DRIVABLE != sx.HALT_UNRECOGNIZED_SCREEN
