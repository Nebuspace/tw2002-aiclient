"""WO-CLASSIFY-FIGHTER-ENCOUNTER-ANCHOR: the toll `Option?` earns a class.

Measured 2026-07-28 while building the combat policy: the bare encounter frame
classified `unknown` (safe), but the SAME dialogue with a sector body painted
above it classified `sector_display` -- an ordinary teachable content class,
handed to the app while the server sat blocked on `Option?`. That is
`money_prompt`'s documented StarDock hazard reproduced for combat, and it is
the *normal* live case, not an edge one.

Hub ruling (a), 2026-07-28: a dedicated `fighter_encounter` class that is
auto-action-eligible WHEN ARMED, owned by `fighter_toll_policy` -- the shape
`DECISIONS.md` §A.2's clarification blesses. Naming-and-forbidding it instead
would close the hole by making Max's ratified Retreat/Attack gate unreachable.

The load-bearing pins here are the ones about what must NOT change: the class
vocabulary is monotone in the dangerous direction (every label added moves a
screen from "must escalate" to "may be taught"), so an anchor that steals from
a driven class is a worse defect than the one it fixes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient.session import fighter_toll_policy as ftp
from tw2002_aiclient.session.classify import (
    NEVER_AUTO_ACTION_CLASSES,
    _RETURNABLE_CLASSES,
    classify_screen,
)

FIXTURES = Path(__file__).parent / "fixtures"

OPTION = "Option? (A,D,I,R,S,?):?"
OPTION_PAY = "Option? (A,D,I,R,P,S,?):?"


def _classify(text: str) -> str:
    lines = [r for r in text.splitlines() if r.strip()]
    return classify_screen(text, lines[-1].strip() if lines else "")


# --- the finding table, all four rows ------------------------------------


def test_the_bare_encounter_is_named_instead_of_unknown():
    assert _classify(f"Corp fighters block your path.\nYour fighters: 9 vs. theirs: 1\n{OPTION}") == (
        "fighter_encounter"
    )


def test_the_toll_banner_variant_with_pay_offered_is_the_same_class():
    assert _classify(f"Fighters: 4 (Somecorp) [Toll]\n{OPTION_PAY}") == "fighter_encounter"


def test_the_regression_that_motivated_this_wo():
    """THE hole: a sector body above the prompt used to win as `sector_display`,
    a teachable class over a server blocked on a combat question."""
    frame = f"Sector  : 42 in uncharted space.\nCorp fighters block your path.\n{OPTION}"
    assert _classify(frame) == "fighter_encounter"


def test_the_quantity_frame_stays_money_prompt():
    """Hub ruling: the policy owns the guarded quantity step under §A.2's
    'bounded quantity chain steps' exemption WITHOUT the class changing.
    Moving it would subtract a screen from the never-auto-action set that every
    other quantity screen shares, for no gain."""
    assert _classify("How many fighters do you wish to use (0 to 250) [0]?") == "money_prompt"


# --- what must NOT change ------------------------------------------------


def test_a_spent_encounter_in_scrollback_never_steals_a_live_command_prompt():
    """Gate anchors match the PROMPT LINE, so a screen whose live prompt is an
    ordinary Command prompt keeps `main_command` even with a resolved `Option?`
    sitting in the history above it. Pinned because the reverse -- claiming a
    live ship prompt as a combat screen -- would stall the explore loop."""
    frame = f"Corp fighters block your path.\n{OPTION}\nYou retreat.\nCommand [TL=0]:[42] (?=Help)? :"
    assert _classify(frame) == "main_command"


def test_a_bare_option_prompt_is_not_claimed():
    """WO constraint: do not widen to bare `Option?`. The letter tuple IS the
    specificity -- other TW screens share the bare shape, and claiming them
    would tell the app it knows a screen it cannot vouch for."""
    for foreign in ("Option? ", "Option? (Y,N):?", "Option? (A,B,C):?", "Enter your Option? "):
        assert _classify(f"Some screen.\n{foreign}") != "fighter_encounter"


def test_the_anchor_steals_no_captured_fixture():
    """Blast radius: NO real captured screen may become an encounter. This is
    the check that matters -- the vocabulary only ever moves screens toward
    'teachable', so a stolen fixture is a regression the class count hides."""
    examined, stolen = [], []
    for p in sorted(FIXTURES.iterdir()):
        if not p.is_file() or p.suffix != ".txt":
            continue
        examined.append(p.name)
        if _classify(p.read_text(errors="replace")) == "fighter_encounter":
            stolen.append(p.name)
    # Pin the POPULATION, not just the verdict: a moved fixture dir or a suffix
    # change would make the loop examine nothing and report a confident green.
    assert len(examined) >= 20, f"fixture corpus shrank -- only examined {examined}"
    assert stolen == []


# --- the ruling, encoded -------------------------------------------------


def test_the_class_is_armed_eligible_not_never_auto_action():
    """Ruling (a). If this ever flips, Max's ratified auto-Retreat/Attack gate
    becomes unreachable and the guard can never fire."""
    assert "fighter_encounter" in _RETURNABLE_CLASSES
    assert "fighter_encounter" not in NEVER_AUTO_ACTION_CLASSES
    assert NEVER_AUTO_ACTION_CLASSES == frozenset({"money_prompt"})


# --- the twin ------------------------------------------------------------


TWIN_FRAMES = (
    OPTION,
    OPTION_PAY,
    "Option? (A,D,I,R,S,?)",  # no trailing `:?` -- classifier yes, policy no
    "Option ? (A,D,I,R,S,?):?",  # space before `?` -- classifier yes, policy no
    "Option?(A,D,I,R,S,?) : ?",  # both
    "Option? (Y,N):?",
    "Option? ",
    "Command [TL=0]:[1] (?=Help)? :",
)


@pytest.mark.parametrize("prompt", TWIN_FRAMES)
def test_the_policy_can_never_act_on_a_screen_the_classifier_did_not_name(prompt):
    """`fighter_toll_policy._OPTION_PROMPT_RE` and this module's anchor are two
    independent regexes for ONE wire shape, living in two modules with nothing
    forcing them to stay in step. Measured: they are NOT equal -- the policy
    additionally requires a trailing `:?` and a literal `Option?`, so frames 3
    and 4 above match here and not there.

    So equality is the wrong thing to pin; DIRECTION is the safety property.
    The dangerous direction is the policy recognising an encounter the
    classifier called something else -- that is the original hole (a combat
    screen wearing a teachable label). The harmless direction is the classifier
    naming one the policy declines: `decide_encounter` then returns
    `key=None`/`not_encounter`, so nothing is sent and the screen escalates.

    Pinned as an implication rather than a table so it keeps its teeth when
    either regex is edited. Deduplicating the two is a policy wire, which this
    WO excludes -- this pin is what keeps the duplication honest meanwhile.
    """
    frame = f"Corp fighters block your path.\nYour fighters: 9 vs. theirs: 1\n{prompt}"
    policy_detects = ftp.parse_encounter(frame, prompt).detected
    if policy_detects:
        assert _classify(frame) == "fighter_encounter", (
            "policy would act on a screen the classifier did not name an encounter"
        )


def test_the_twin_direction_pin_is_not_vacuous():
    """The implication above is only worth having if its antecedent fires.
    Without this, narrowing the policy regex to nothing would leave every
    direction pin trivially true and silently green."""
    detected = [
        p for p in TWIN_FRAMES if ftp.parse_encounter(f"x\n{p}", p).detected
    ]
    assert len(detected) >= 3, f"policy detected too few twin frames: {detected}"
