"""WO-FIX-EXPLORE-NO-DEFENSIVE-POSTURE-BEFORE-UNCHARTED — decision pins."""

from __future__ import annotations

from tw2002_aiclient.session.explore_defensive_posture import (
    FIGHTER_FLOOR,
    decide_defensive_posture,
)


def test_seek_when_under_floor_dealer_near_and_funded():
    d = decide_defensive_posture(
        fighters_aboard=6,
        credits=100_000,
        hops_to_dealer=3,
        turns_remaining=25_000,
    )
    assert d.action == "seek_dealer"
    assert d.qty == FIGHTER_FLOOR - 6
    assert d.hops_to_dealer == 3
    assert d.stack_cost == d.qty * 100


def test_skip_when_no_dealer():
    d = decide_defensive_posture(
        fighters_aboard=6,
        credits=100_000,
        hops_to_dealer=None,
        turns_remaining=25_000,
    )
    assert d.action == "skip_unreachable"


def test_skip_when_dealer_too_far():
    d = decide_defensive_posture(
        fighters_aboard=6,
        credits=100_000,
        hops_to_dealer=50,
        turns_remaining=25_000,
    )
    assert d.action == "skip_scarce_turns"


def test_already_sufficient():
    d = decide_defensive_posture(
        fighters_aboard=20,
        credits=100_000,
        hops_to_dealer=1,
        turns_remaining=100,
    )
    assert d.action == "already_sufficient"
    assert d.qty == 0


def test_skip_unknown_fighters():
    d = decide_defensive_posture(
        fighters_aboard=None,
        credits=100_000,
        hops_to_dealer=0,
        turns_remaining=100,
    )
    assert d.action == "skip_unknown_fighters"


def test_skip_cannot_afford_after_cash_floor():
    # 10_050 credits, cash floor 10_000 → only 50 discretionary; < 100/ea.
    d = decide_defensive_posture(
        fighters_aboard=6,
        credits=10_050,
        hops_to_dealer=0,
        turns_remaining=100,
    )
    assert d.action == "skip_cannot_afford"


def test_at_dealer_hops_zero_still_seek():
    d = decide_defensive_posture(
        fighters_aboard=6,
        credits=100_000,
        hops_to_dealer=0,
        turns_remaining=100,
    )
    assert d.action == "seek_dealer"
    assert d.hops_to_dealer == 0
