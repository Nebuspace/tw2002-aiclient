"""WO-FIX-LOGIN-ANSI-SPLASH-UNHANDLED: sursum_corda connect splash."""

from __future__ import annotations

from tw2002_aiclient.session.classify import classify_screen
from tw2002_aiclient.session import login as login_mod
from tw2002_aiclient.session.login import _decide

CAPTURED = (
    "ooooo                  .    The TradeWarriors Game          *             ooooo\n"
    "oooooooo       Please press A B or C to play after connect.        oooooooooo\n"
    "ooooooooooo     .  Please Hang Up after quitting the game.       .  ooooooooooo\n"
    "Timed out...\n"
)


def test_captured_connect_splash_classifies():
    assert classify_screen(CAPTURED, "Timed out...") == "connect_splash"


def test_decide_sends_profile_letter_when_abc():
    profile = login_mod.LoginProfile(
        name="scout_sursum",
        handle="Ranger7",
        game_letter="B",
        allow_register=True,
    )
    state = {
        "registering": None,
        "password": None,
        "password_attempts": 0,
        "outer_name_handle_tried": False,
        "alias": None,
        "alias_attempts": 0,
        "save_alias": None,
    }
    action = _decide(
        "connect_splash",
        CAPTURED,
        "Timed out...",
        profile,
        state,
        get_password=lambda _: None,
        save_password=lambda *_: None,
        session=object(),
    )
    assert action == ("B", False, None)


def test_decide_defaults_to_a_when_letter_not_abc():
    profile = login_mod.LoginProfile(
        name="x",
        handle="H",
        game_letter="T",
        allow_register=True,
    )
    state = {
        "registering": None,
        "password": None,
        "password_attempts": 0,
        "outer_name_handle_tried": False,
        "alias": None,
        "alias_attempts": 0,
        "save_alias": None,
    }
    action = _decide(
        "connect_splash",
        CAPTURED,
        "Timed out...",
        profile,
        state,
        get_password=lambda _: None,
        save_password=lambda *_: None,
        session=object(),
    )
    assert action == ("A", False, None)
