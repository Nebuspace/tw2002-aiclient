"""WO-LOGIN-SCROLLBACK-SEARCH-AUDIT: pins for whole-grid vs scoped login
searches in ``_decide``.

- ``SHOW_LOG_RE`` (interjection_registry): intentional whole-grid — phrase
  in the BODY (not only the last line) must still fire.
- ``INACTIVITY_RE`` / ``CLEAR_AVOIDS_RE``: scoped to prompt /
  ``_option_block_above_prompt`` — stale banner above a blank separator
  must NOT fire against an unrelated current prompt; fresh body text in
  the current block still must.
- ``_OUTER_NAME_REJECTED_RE`` / ``_PLANET_NAME_PROMPT_RE``: prompt-gate
  durability — rejection / planet-name body text must not act when the
  prompt gate is absent.
"""

from __future__ import annotations

from tw2002_aiclient.session import login
from tw2002_aiclient.session.interjection_registry import (
    CLEAR_AVOIDS_RE,
    INACTIVITY_RE,
    SHOW_LOG_RE,
)


def _state():
    return {
        "registering": None,
        "password": None,
        "password_attempts": 0,
        "outer_name_handle_tried": False,
    }


class _S:
    game_select_answered = False
    game_select_letter_sent = False


def _decide(cls, text, prompt, state=None, **profile_kw):
    profile = login.LoginProfile(
        name=profile_kw.pop("name", "scrollback"),
        handle=profile_kw.pop("handle", "AEGIS"),
        game_letter=profile_kw.pop("game_letter", "F"),
        **profile_kw,
    )
    st = state if state is not None else _state()
    return login._decide(
        cls, text, prompt, profile, st, lambda n: None, lambda n, p: None, _S()
    )


def test_show_log_matches_body_not_only_last_line():
    """Intentional whole-grid: 'show today's log' in the body (above an
    unrelated last line) must still answer N."""
    text = (
        "Would you like to show today's log? (Y/N) [N]\n"
        "\n"
        "Command [TL=00:00:00]:\n"
    )
    prompt = "Command [TL=00:00:00]:"
    assert SHOW_LOG_RE.search(text)
    assert not SHOW_LOG_RE.search(prompt)
    assert not SHOW_LOG_RE.search(text.splitlines()[-1])
    assert _decide("main_command", text, prompt) == ("N", False, None)


def test_inactivity_matches_body_not_only_last_line():
    """Fresh inactivity in the current option-block BODY (not only the
    last/prompt line) must still send a blank keepalive Enter."""
    # No blank between banner and prompt → option-block includes the body.
    text = (
        "*** INACTIVITY WARNING ***\n"
        "You will be disconnected for critical inactivity.\n"
        "Command [TL=00:00:00]:\n"
    )
    prompt = "Command [TL=00:00:00]:"
    assert INACTIVITY_RE.search(text)
    assert not INACTIVITY_RE.search(prompt)
    assert not INACTIVITY_RE.search(text.splitlines()[-1])
    block = login._option_block_above_prompt(text, prompt)
    assert INACTIVITY_RE.search(block)
    assert _decide("main_command", text, prompt) == ("", False, None)


def test_inactivity_stale_scrollback_does_not_blank_enter():
    """Accept #4: stale inactivity above a blank separator + unrelated
    current block must NOT produce a blank send (whole-grid was unsafe)."""
    text = (
        "*** INACTIVITY WARNING ***\n"
        "You will be disconnected for critical inactivity.\n"
        "\n"
        "Sector 123\n"
        "Command [TL=00:00:00]:\n"
    )
    prompt = "Command [TL=00:00:00]:"
    assert INACTIVITY_RE.search(text)
    block = login._option_block_above_prompt(text, prompt)
    assert "inactivity" not in block.lower()
    assert _decide("main_command", text, prompt) is None


def test_clear_avoids_stale_scrollback_does_not_fire():
    """Stale-scrollback hazard closed: prior 'clear avoids?' above a blank
    separator must not fire when the current option-block is unrelated.

    Same structural discipline as MODULE_ENTRY / ``_option_block_above_prompt``:
    once a current block line is collected, the blank stops the walk so
    scrollback above is excluded. Whole-grid ``.search(text)`` would have
    returned N here.
    """
    text = (
        "Do you wish to clear some avoids? (Y/N)\n"
        "\n"
        "Sector 123\n"
        "Command [TL=00:00:00]:\n"
    )
    prompt = "Command [TL=00:00:00]:"
    # Whole-grid would still see the stale question…
    assert CLEAR_AVOIDS_RE.search(text)
    # …but prompt and the scoped option-block must not.
    assert not CLEAR_AVOIDS_RE.search(prompt)
    block = login._option_block_above_prompt(text, prompt)
    assert "clear" not in block.lower()
    assert not CLEAR_AVOIDS_RE.search(block)
    assert _decide("main_command", text, prompt) is None


def test_outer_name_rejected_does_not_fire_without_prompt_gate():
    """Accept #5: rejection body text must not take the outer-name rejection
    path when ``prompt`` fails ``_OUTER_NAME_PROMPT_RE``."""
    text = (
        "A login name is required.\n"
        "Enter your name:\n"
    )
    prompt = "Enter your name:"
    assert login._OUTER_NAME_REJECTED_RE.search(text)
    assert not login._OUTER_NAME_PROMPT_RE.search(prompt)
    state = _state()
    action = _decide("login_name", text, prompt, state=state, handle="AEGIS")
    # Normal character-name send — rejection retry must not latch.
    assert state["outer_name_handle_tried"] is False
    assert action == ("AEGIS", False, None)


def test_planet_name_does_not_fire_without_box_prompt_gate():
    """Accept #5: 'name your home planet' in ``text`` must not name the
    planet when ``prompt`` is not the input-box marker."""
    text = (
        "What do you wish to name your home planet?\n"
        "Command [TL=00:00:00]:\n"
    )
    prompt = "Command [TL=00:00:00]:"
    assert login._PLANET_NAME_PROMPT_RE.search(text)
    assert not login._PLANET_NAME_BOX_RE.search(prompt)
    action = _decide("unknown", text, prompt, handle="AEGIS", planet_name="Anchorage")
    assert action is None
    assert action != ("Anchorage", False, None)
