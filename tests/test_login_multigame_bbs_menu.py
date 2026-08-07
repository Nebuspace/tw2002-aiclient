"""WO-FIX-LOGIN-MULTIGAME-BBS-MENU-UNHANDLED: TWGS <L> door as menu."""

from __future__ import annotations

from tw2002_aiclient.session import login as login_mod
from tw2002_aiclient.session.login import _decide, _menu_offers_game_letter

MOONBASE_MENU = (
    "Trade Wars 2002 Game Server v2.20b\n"
    "<A> Art of War                      <B> Battlestar Galactica\n"
    "<T> TradeWars Academy               <U> USO4\n"
    "<Q> Quit\n"
)


def test_menu_offers_t_for_academy():
    assert _menu_offers_game_letter(MOONBASE_MENU, "<Q> Quit", "T")
    assert not _menu_offers_game_letter(MOONBASE_MENU, "<Q> Quit", "Z")


def test_menu_offers_ignores_stale_letter_above_blank():
    """Stale ``<F>`` above a blank must not vouch for the current block."""
    text = (
        "<F> Bob the Builder\n"
        "Select a game :\n"
        "\n"
        "T - Play Trade Wars 2002\n"
        "I - Introduction & Help\n"
        "Enter your choice:\n"
    )
    assert not _menu_offers_game_letter(text, "Enter your choice:", "F")


def test_module_entry_t_is_not_multigame_letter_send():
    from tw2002_aiclient.session.login import _is_multigame_letter_menu_send

    text = (
        "T - Play Trade Wars 2002\n"
        "I - Introduction & Help\n"
        "Enter your choice:\n"
    )
    assert not _is_multigame_letter_menu_send("menu", "T", text, "Enter your choice:")
    assert _is_multigame_letter_menu_send(
        "menu", "T", MOONBASE_MENU, "<Q> Quit"
    )


def test_decide_menu_sends_configured_letter():
    profile = login_mod.LoginProfile(
        name="scout_moonbase",
        handle="Nomad11",
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

    class _Sess:
        game_select_answered = False

    action = _decide(
        "menu",
        MOONBASE_MENU,
        "<Q> Quit",
        profile,
        state,
        get_password=lambda _: None,
        save_password=lambda *_: None,
        session=_Sess(),
    )
    assert action == ("T", False, None)


def test_decide_menu_refuses_letter_not_on_menu():
    profile = login_mod.LoginProfile(
        name="x",
        handle="H",
        game_letter="Z",
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

    class _Sess:
        game_select_answered = False

    action = _decide(
        "menu",
        MOONBASE_MENU,
        "<Q> Quit",
        profile,
        state,
        get_password=lambda _: None,
        save_password=lambda *_: None,
        session=_Sess(),
    )
    assert action is None
