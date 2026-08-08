"""WO-FIX-LOGIN-FIGHTER-ENCOUNTER-UNHANDLED: a fresh registration can land in
a hostile starting sector before `ensure` ever hands off to `sector_explore`'s
own automaton. `_decide` must resolve `fighter_encounter` through the SAME
guarded `fighter_toll_policy` engine that module already fires under, and
must halt (never guess, never Pay) exactly when that policy halts.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import login as login_mod
from tw2002_aiclient.session.login import LoginError, _decide

OPTION = "Option? (A,D,I,R,S,?):?"


def _profile():
    return login_mod.LoginProfile(
        name="scout_sursum",
        handle="Ranger7",
        game_letter="B",
        allow_register=True,
    )


def _state():
    return {
        "registering": None,
        "password": None,
        "password_attempts": 0,
        "outer_name_handle_tried": False,
        "alias": None,
        "alias_attempts": 0,
        "save_alias": None,
    }


def _decide_fighter(text, prompt=OPTION):
    return _decide(
        "fighter_encounter",
        text,
        prompt,
        _profile(),
        _state(),
        get_password=lambda _: None,
        save_password=lambda *_: None,
        session=object(),
    )


def test_winnable_npc_fight_attacks():
    frame = f"You have to destroy the fighters to remain in this sector.\nYour fighters: 9 vs. theirs: 1\n{OPTION}"
    action = _decide_fighter(frame)
    assert action == ("A", False, None)


def test_below_gate_retreats():
    frame = f"You have to destroy the fighters to remain in this sector.\nYour fighters: 1 vs. theirs: 9\n{OPTION}"
    action = _decide_fighter(frame)
    assert action == ("R", False, None)


def test_pvp_halts_with_login_error():
    frame = f"Commander Rax is here.\nYour fighters: 500 vs. theirs: 1\n{OPTION}"
    with pytest.raises(LoginError, match="fighter_encounter_halt:pvp_hard_stop"):
        _decide_fighter(frame)


def test_unparsed_counts_retreats_rather_than_guessing():
    frame = f"Corp fighters block your path.\n{OPTION}"
    action = _decide_fighter(frame)
    assert action == ("R", False, None)


def test_forbidden_pay_key_is_structurally_unreachable():
    assert "P" not in login_mod.FIGHT_LETTER_ALLOWLIST
    assert "P" in login_mod.FIGHT_FORBIDDEN_KEYS
