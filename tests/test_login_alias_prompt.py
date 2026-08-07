"""WO-FIX-LOGIN-ALIAS-PROMPT-UNHANDLED: classify + bounded alias mint."""

from __future__ import annotations

from tw2002_aiclient.session.classify import classify_screen
from tw2002_aiclient.session import login as login_mod
from tw2002_aiclient.session.login import LoginError, _decide, _fresh_alias


CAPTURED_ALIAS = (
    "Sorry, you cannot use the name Wayfind2.\n"
    "You must use an Alias.\n"
    "\n"
    "What Alias do you want to use?\n"
)


def test_captured_alias_prompt_classifies_login_alias():
    prompt = "What Alias do you want to use?"
    assert classify_screen(CAPTURED_ALIAS, prompt) == "login_alias"


def test_fresh_alias_appends_suffix_within_max_len():
    alias = _fresh_alias("Wayfind2")
    assert alias.startswith("Wayfind2")
    assert len(alias) == len("Wayfind2") + login_mod._ALIAS_SUFFIX_LEN
    assert len(alias) <= login_mod._ALIAS_MAX_LEN


def test_decide_login_alias_sends_minted_alias_and_persists():
    saved = []
    profile = login_mod.LoginProfile(
        name="scout",
        handle="Wayfind2",
        game_letter="A",
        allow_register=True,
    )
    state = {
        "registering": True,
        "password": None,
        "password_attempts": 0,
        "outer_name_handle_tried": False,
        "alias": None,
        "alias_attempts": 0,
        "save_alias": lambda name, alias: saved.append((name, alias)),
    }

    action = _decide(
        "login_alias",
        CAPTURED_ALIAS,
        "What Alias do you want to use?",
        profile,
        state,
        get_password=lambda _: None,
        save_password=lambda *_: None,
        session=object(),
    )
    assert action is not None
    send, secret, _hint = action
    assert secret is False
    assert send.startswith("Wayfind2")
    assert state["alias"] == send
    assert state["alias_attempts"] == 1
    assert saved == [("scout", send)]


def test_alias_retries_exhausted_raises_named_error():
    profile = login_mod.LoginProfile(
        name="scout",
        handle="Wayfind2",
        game_letter="A",
        allow_register=True,
    )
    state = {
        "registering": True,
        "password": None,
        "password_attempts": 0,
        "outer_name_handle_tried": False,
        "alias": None,
        "alias_attempts": login_mod._MAX_ALIAS_RETRIES,
        "save_alias": None,
    }
    try:
        _decide(
            "login_alias",
            CAPTURED_ALIAS,
            "What Alias do you want to use?",
            profile,
            state,
            get_password=lambda _: None,
            save_password=lambda *_: None,
            session=object(),
        )
        raise AssertionError("expected LoginError")
    except LoginError as exc:
        assert "alias_retries_exhausted" in str(exc)
