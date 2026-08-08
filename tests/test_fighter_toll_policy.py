"""Pins for the NPC fighter-toll encounter policy.

Contract: ``canon/strategy/toll-and-defense.md`` § Schema — the decision
parameters, § Toll-dialogue guard behavior (I5), § NPC / PvP boundary (hard).

Three of these are falsification pins rather than behaviour tests — they exist
to go red if a specific *forbidden* implementation comes back:

* :func:`test_unreadable_quantity_never_commits_max_avail` fails if the
  archived ``return max_avail`` fallback is restored.
* :func:`test_every_halting_decision_withholds_a_keystroke` fails if any STOP
  is ever paired with a key, which is how a halt gets silently masked.
* :func:`test_band_gate_is_independent_of_the_ratio_gate` fails if the enemy
  band is dropped and the share gate is left to carry the decision alone.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import fighter_toll_policy as ftp

OPTION = "Option? (A,D,I,R,S,?):?"
OPTION_WITH_PAY = "Option? (A,D,I,R,P,S,?):?"


def _frame(yours: int | None = None, theirs: int | None = None, prompt: str = OPTION) -> str:
    lines = ["Corp fighters block your path."]
    if yours is not None and theirs is not None:
        lines.append(f"Your fighters: {yours} vs. theirs: {theirs}")
    lines.append(prompt)
    return "\n".join(lines)


def _qty_frame(max_avail: int, default: int = 0, vs: tuple[int, int] | None = None) -> str:
    lines = []
    if vs is not None:
        lines.append(f"Your fighters: {vs[0]} vs. theirs: {vs[1]}")
    lines.append(f"How many fighters do you wish to use (0 to {max_avail}) [{default}]?")
    return "\n".join(lines)


# --- force_share itself ----------------------------------------------------


def test_force_share_is_a_share_of_present_forces():
    assert ftp.force_share(9, 1) == pytest.approx(0.90)
    assert ftp.force_share(89, 1) == pytest.approx(0.98889, abs=1e-5)
    assert ftp.force_share(1, 1) == pytest.approx(0.50)


def test_force_share_refuses_an_empty_engagement_rather_than_guessing():
    # Any fallback here would be a lie in one direction or the other, and the
    # dangerous direction (1.0) reads as maximum confidence.
    with pytest.raises(ValueError):
        ftp.force_share(0, 0)


# --- the three branches ----------------------------------------------------


def test_attacks_an_npc_toll_at_or_above_the_gate():
    d = ftp.decide_encounter(
        ftp.parse_encounter(_frame(9, 1)),
        attack_approved=True,
    )
    assert (d.key, d.halt) == ("A", False)
    assert d.reason.startswith("attack_npc:")


@pytest.mark.parametrize("yours,theirs", [(89, 1), (60, 1), (20, 1)])
def test_max_ratified_examples_all_fight(yours, theirs):
    # The examples Max gave when ratifying the 0.90 gate.
    assert (
        ftp.decide_encounter(
            ftp.parse_encounter(_frame(yours, theirs)),
            attack_approved=True,
        ).key
        == "A"
    )


def test_unapproved_winnable_toll_retreats():
    """FALSIFICATION: force_share-passing Attack must not fire without approval."""
    d = ftp.decide_encounter(ftp.parse_encounter(_frame(9, 1)))
    assert (d.key, d.halt) == ("R", False)
    assert d.reason == "attack_behavior_not_approved"


def test_next_encounter_input_forwards_attack_approved():
    d = ftp.next_encounter_input(
        _frame(9, 1),
        attack_approved=ftp.FIGHTER_TOLL_ATTACK_BEHAVIOR_APPROVED,
    )
    assert (d.key, d.halt) == ("A", False)
    assert d.reason.startswith("attack_npc:")


def test_retreats_just_below_the_gate():
    # 8:1 -> 0.888..., the first losing step down from 9:1.
    d = ftp.decide_encounter(ftp.parse_encounter(_frame(8, 1)))
    assert d.key == "R"
    assert d.reason.startswith("force_share_below_gate:")


def test_band_gate_is_independent_of_the_ratio_gate():
    """FALSIFICATION: 90 v 10 clears the share gate exactly and must still retreat.

    A ratio alone cannot express canon's `winnable_enemy_band`. If the band
    check is deleted this case starts attacking ten enemies at once.
    """
    state = ftp.parse_encounter(_frame(90, 10))
    assert ftp.force_share(90, 10) == pytest.approx(0.90)  # share gate satisfied
    d = ftp.decide_encounter(state)
    assert d.key == "R"
    assert d.reason.startswith("enemy_band_exceeded:")


# --- missing is not zero ---------------------------------------------------


def test_unparsed_counts_retreat_at_the_option_prompt():
    d = ftp.decide_encounter(ftp.parse_encounter(_frame()))
    assert (d.key, d.reason) == ("R", "unparsed_counts_retreat")


def test_a_parsed_zero_enemy_is_data_not_absence():
    present = ftp.parse_encounter(_frame(10, 0))
    assert present.counts_present is True
    assert ftp.decide_encounter(present).reason == "no_enemy_retreat"
    absent = ftp.parse_encounter(_frame())
    assert absent.counts_present is False


def test_zero_of_our_own_fighters_retreats():
    assert ftp.decide_encounter(ftp.parse_encounter(_frame(0, 1))).reason == "no_fighters_retreat"


def test_toll_banner_gives_only_the_enemy_side_so_we_do_not_guess_ours():
    frame = f"Fighters: 4 (Somecorp) [Toll]\n{OPTION}"
    state = ftp.parse_encounter(frame)
    assert (state.yours, state.theirs) == (None, 4)
    assert state.counts_present is False
    assert ftp.decide_encounter(state).key == "R"


# --- the hard boundaries ---------------------------------------------------


def test_pvp_is_a_hard_stop_and_the_math_never_runs():
    frame = f"Commander Rax is here.\nYour fighters: 500 vs. theirs: 1\n{OPTION}"
    d = ftp.decide_encounter(ftp.parse_encounter(frame))
    # Overwhelming odds -- would be a clear Attack if the boundary were soft.
    assert (d.key, d.halt, d.reason) == (None, True, "pvp_hard_stop")


def test_pay_is_never_selected_even_when_the_key_is_offered():
    for frame, approved in (
        (_frame(9, 1, OPTION_WITH_PAY), True),
        (_frame(1, 9, OPTION_WITH_PAY), True),
        (_frame(prompt=OPTION_WITH_PAY), False),
    ):
        d = ftp.decide_encounter(
            ftp.parse_encounter(frame),
            attack_approved=approved,
        )
        assert d.key != "P"


def test_an_unratified_threshold_never_fights():
    d = ftp.decide_encounter(
        ftp.parse_encounter(_frame(1000, 1)), force_share_auto_attack=None
    )
    assert (d.key, d.reason) == ("R", "threshold_unset_retreat")


# --- the quantity prompt ---------------------------------------------------


def test_unreadable_quantity_never_commits_max_avail():
    """FALSIFICATION: the archived ``return max_avail`` fallback must stay dead.

    A qty screen routinely omits the vs-line, so counts present at ``Option?``
    prove nothing here. Committing the full complement on unreadable counts is
    the largest irreversible spend at the step that cannot be undone.
    """
    d = ftp.decide_quantity(_qty_frame(250))
    assert d.detected is True
    assert d.halt is True
    assert d.key is None
    assert d.key != "250"  # the exact forbidden answer, named
    assert d.reason == "qty_counts_unreadable_stop"


def test_quantity_commits_the_enemy_count_not_everything_available():
    d = ftp.decide_quantity(_qty_frame(250, vs=(200, 2)))
    assert d.key == "2"
    assert d.key != "250"


def test_quantity_halts_when_the_band_is_exceeded():
    d = ftp.decide_quantity(_qty_frame(250, vs=(900, 9)))
    assert (d.key, d.halt) == (None, True)


def test_quantity_prompt_wins_when_both_frames_are_on_screen():
    both = _frame(9, 1) + "\n" + _qty_frame(50, vs=(9, 1))
    d = ftp.next_encounter_input(both)
    # Answering the stale Option? here is what re-sends Attack at a live
    # quantity prompt, which was observed looping forever.
    assert d.key == "1"
    assert d.reason.startswith("qty_commit:")




def test_quantity_never_commits_past_reserve_floor():
    """FALSIFICATION: auto-commit must leave DEFAULT_FIGHTER_RESERVE aboard.

    max_avail=6, theirs=2 (inside band), reserve=5 → spendable=1 < needed=2 → halt.
    Never commit the full complement ("6").
    """
    d = ftp.decide_quantity(_qty_frame(6, vs=(6, 2)), reserve=5)
    assert d.halt is True
    assert d.key is None
    assert d.key != "6"
    assert d.reason.startswith("qty_reserve_floor_stop:")


def test_quantity_clamps_commit_to_spendable_under_reserve():
    """theirs fits under spendable — commit theirs, not max_avail."""
    d = ftp.decide_quantity(_qty_frame(20, vs=(20, 2)), reserve=5)
    assert d.halt is False
    assert d.key == "2"
    assert "reserve=5" in d.reason


def test_quantity_default_reserve_matches_module_constant():
    d = ftp.decide_quantity(_qty_frame(6, vs=(6, 2)))
    # DEFAULT_FIGHTER_RESERVE=5 → spendable=1 < needed=2 → halt
    assert d.halt is True
    assert d.key is None
    assert "qty_reserve_floor_stop" in d.reason


def test_next_encounter_input_passes_reserve_into_quantity():
    # max_avail=5, reserve=5 → spendable=0 < theirs=1 → halt via reserve path
    both = _frame(9, 1) + "\n" + _qty_frame(5, vs=(9, 1))
    d = ftp.next_encounter_input(both, reserve=5)
    assert d.halt is True
    assert d.key is None
    assert d.reason.startswith("qty_reserve_floor_stop:")


# --- structural pins -------------------------------------------------------


def test_every_halting_decision_withholds_a_keystroke():
    """FALSIFICATION: a STOP that also carries a key is a masked halt."""
    frames = [
        f"Commander Rax is here.\nYour fighters: 5 vs. theirs: 1\n{OPTION}",
        _qty_frame(250),
        _qty_frame(250, vs=(900, 9)),
        _qty_frame(0, vs=(9, 1)),
    ]
    seen_halt = False
    for f in frames:
        d = ftp.next_encounter_input(f)
        if d.halt:
            seen_halt = True
            assert d.key is None, f"halting decision carried key {d.key!r}: {d.reason}"
    assert seen_halt, "fixture no longer produces any halt -- the pin went vacuous"


def test_a_non_encounter_frame_is_not_detected():
    d = ftp.next_encounter_input("Command [TL=00:00:00]:[1] (?=Help)? :")
    assert (d.detected, d.key, d.halt) == (False, None, False)
