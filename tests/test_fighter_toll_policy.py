"""WO-FIGHTER-FLOOR-TOLL — fighter reserve + Option? policy tests.

Folds/supersedes parked WO-FIGHTER-AUTO-R: hopeless Option? → R, never P.
"""

from twclient.fighter_toll_policy import (
    DEFAULT_AUTO_ATTACK_MAX_ENEMY,
    DEFAULT_FIGHTER_RESERVE,
    FighterOptionState,
    clamp_deploy_or_sell_qty,
    decide_fighter_option,
    decide_from_screen,
    max_deployable,
    parse_fighter_option,
)

_OPTION_SCREEN = (
    "Sector  : 8578 in uncharted space.\n"
    "Fighters: 1 (belong to Corp#1, New Corp) [Toll]\n"
    "You have to destroy the fighters or pay their toll to remain in this sector.\n"
    "Your fighters: {yours} vs. theirs: {theirs}\n"
    "Option? (A,D,I,R,P,S,?):?"
)

# Live TWGS toll omits Pay — matches hud_seed / Ona cold-start.
_OPTION_SCREEN_NO_PAY = (
    "Sector  : 8578 in uncharted space.\n"
    "You have to destroy the fighters\n"
    "Your fighters: {yours} vs. theirs: {theirs}\n"
    "Option? (A,D,I,R,S,?):?"
)


def test_default_reserve_is_small_and_documented():
    assert DEFAULT_FIGHTER_RESERVE == 5
    assert DEFAULT_AUTO_ATTACK_MAX_ENEMY == 3


def test_reserve_preserved_on_deploy_sell_clamp():
    assert max_deployable(12, reserve=5) == 7
    assert clamp_deploy_or_sell_qty(100, 12, reserve=5) == 7
    assert clamp_deploy_or_sell_qty(3, 12, reserve=5) == 3
    assert clamp_deploy_or_sell_qty(100, 4, reserve=5) == 0
    assert clamp_deploy_or_sell_qty(100, 5, reserve=5) == 0


def test_parse_fighter_option_counts():
    text = _OPTION_SCREEN.format(yours=0, theirs=1)
    st = parse_fighter_option(text)
    assert st.detected is True
    assert st.yours == 0
    assert st.theirs == 1


def test_parse_ignores_non_option_screens():
    st = parse_fighter_option("Sector : 100\nYour offer [500] ?")
    assert st.detected is False


def test_single_fighter_toll_attacks_when_reserve_allows():
    d = decide_from_screen(_OPTION_SCREEN.format(yours=5, theirs=1))
    assert d.detected is True
    assert d.key == "A"
    assert "attack_winnable" in d.reason


def test_newplayer_toll_no_pay_prompt_attacks_favorable_odds():
    """WO-FIGHTER-TOLL-NEWPLAYER: live Option? omits P; 30 vs 1 → Attack."""
    text = _OPTION_SCREEN_NO_PAY.format(yours=30, theirs=1)
    st = parse_fighter_option(text)
    assert st.detected is True
    assert st.yours == 30
    assert st.theirs == 1
    d = decide_from_screen(text)
    assert d.key == "A"
    assert "attack_winnable" in d.reason


def test_zero_fighters_retreats_never_pay():
    """Folded WO-FIGHTER-AUTO-R: 0 vs 1 → R, never P."""
    d = decide_from_screen(_OPTION_SCREEN.format(yours=0, theirs=1))
    assert d.key == "R"
    assert d.key != "P"


def test_multi_fighter_hopeless_retreats():
    d = decide_from_screen(_OPTION_SCREEN.format(yours=2, theirs=50))
    assert d.key == "R"


def test_few_enemies_but_outgunned_retreats():
    d = decide_from_screen(_OPTION_SCREEN.format(yours=1, theirs=3))
    assert d.key == "R"


def test_unparsed_option_holds():
    text = "Option? (A,D,I,R,P,S,?):?\n(no fighter counts here)"
    d = decide_from_screen(text)
    assert d.detected is True
    assert d.key is None
    assert d.reason == "unparsed_fighter_counts"


def test_decide_never_selects_pay_even_if_allow_pay_kwarg_present():
    d = decide_fighter_option(
        FighterOptionState(detected=True, yours=0, theirs=1),
        allow_pay=True,
    )
    assert d.key == "R"
