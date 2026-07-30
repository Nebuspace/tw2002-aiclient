"""`cockpit.chains` -- the `L)chains` popup's pure half (WO-PLAY-AUTOLOOP-START).

No curses, no filesystem: these pin the composer, the selection math, and the
one honesty rule the surface owes -- that an unreadable store is never
rendered as an empty one.

`playable_loops`'s exclusions are pinned individually rather than as a single
count, because "two rows came back" stays green if the wrong two came back.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.cockpit import chains


TWO = {
    "status": "ok",
    "loops": [
        {"name": "ore-run-K7", "steps": 12, "draft": False},
        {"name": "fuel-shuttle", "steps": 8, "draft": False},
    ],
}


def _names(rows):
    return [r["name"] for r in rows]


# ---------------------------------------------------------------- key resolve

def test_l_in_both_cases_opens_the_popup():
    assert chains.resolve_chains_offer_key(ord("l")) is True
    assert chains.resolve_chains_offer_key(ord("L")) is True


def test_key_resolution_is_hardened_like_its_siblings():
    """`True == 1` would match a keycode by accident; the same guard
    `panic.resolve_panic_key` and `resolve_pause_key` carry."""
    for bogus in (True, False, None, "l", "L", 1.0, [], object()):
        assert chains.resolve_chains_offer_key(bogus) is False


def test_other_cluster_letters_do_not_open_the_popup():
    """A/R/T are the teach keys, E explore, G relaunch, P panic, Q quit --
    none of them may fall into this popup."""
    for other in "arteEgGpPqQ":
        if other in "lL":
            continue
        assert chains.resolve_chains_offer_key(ord(other)) is False


# --------------------------------------------------------------- store filter

def test_playable_loops_lists_blessed_macros():
    assert _names(chains.playable_loops(TWO)) == ["ore-run-K7", "fuel-shuttle"]


def test_drafts_are_excluded():
    """A draft is pre-approval; offering it to arm routes around the approval
    it is still waiting for."""
    store = {"status": "ok", "loops": [{"name": "d", "steps": 3, "draft": True}]}
    assert chains.playable_loops(store) == []


def test_zero_step_macros_are_excluded():
    """A macro with no steps cannot replay anything, so a confirm prompt for
    it would name a run that does nothing."""
    store = {"status": "ok", "loops": [{"name": "empty", "steps": 0}]}
    assert chains.playable_loops(store) == []


def test_nameless_rows_are_excluded():
    """The name is what `autoloop_start` sends; a nameless row could only
    ever produce `missing_name`."""
    store = {"status": "ok", "loops": [{"name": "  ", "steps": 4}, {"steps": 4}]}
    assert chains.playable_loops(store) == []


def test_a_malformed_store_yields_no_rows_and_never_raises():
    for bogus in (None, [], "loops", 7, {"loops": "nope"}, {"loops": [None, 3]}):
        assert chains.playable_loops(bogus) == []


def test_rows_are_copied_not_aliased():
    """A caller mutating the returned row must not reach into the store
    result the popup was built from."""
    rows = chains.playable_loops(TWO)
    rows[0]["name"] = "mutated"
    assert TWO["loops"][0]["name"] == "ore-run-K7"


# -------------------------------------------------------------------- status

def test_store_status_passes_through_the_three_known_values():
    for value in ("ok", "partial", "unreadable"):
        assert chains.store_status({"status": value}) == value


def test_an_unknown_or_absent_status_fails_closed_to_unreadable():
    """Fail-closed direction: wrongly saying "unknown" confuses an operator;
    wrongly saying "none taught" tells them their macros are gone."""
    for bogus in ({}, {"status": "fine"}, {"status": None}, None, 7, "ok"):
        assert chains.store_status(bogus) == "unreadable"


# ------------------------------------------------------------------- session

def test_session_starts_closed_and_status_unreadable():
    s = chains.ChainsSession()
    assert s.is_open is False
    assert s.selected() is None
    assert s.status == "unreadable"


def test_open_without_a_status_does_not_claim_ok():
    """A caller who forgets the status gets honest-unknown, not a fabricated
    empty."""
    s = chains.ChainsSession()
    s.open([])
    assert s.status == "unreadable"


def test_cursor_is_clamped_not_wrapped():
    """Wrapping past the end of a list of live-money actions puts a
    different row under a confirm the operator may already be reaching for."""
    s = chains.ChainsSession()
    s.open(chains.playable_loops(TWO), "ok")
    assert s.selected()["name"] == "ore-run-K7"
    s.move(1)
    assert s.selected()["name"] == "fuel-shuttle"
    s.move(1)
    assert s.selected()["name"] == "fuel-shuttle", "cursor wrapped to the top"
    s.move(-5)
    assert s.selected()["name"] == "ore-run-K7"


def test_move_ignores_non_int_deltas_and_never_raises():
    s = chains.ChainsSession()
    s.open(chains.playable_loops(TWO), "ok")
    for bogus in (True, None, "1", 1.5, []):
        s.move(bogus)
    assert s.index == 0


def test_selected_is_none_when_there_is_nothing_to_arm():
    s = chains.ChainsSession()
    s.open([], "ok")
    assert s.selected() is None


def test_close_dismisses_without_losing_the_status():
    s = chains.ChainsSession()
    s.open([], "unreadable")
    s.close()
    assert s.is_open is False
    assert s.status == "unreadable"


# ------------------------------------------------------------------ composers

def test_arm_action_names_the_macro_and_says_one_pass():
    """Chains arm has no rule scope — honest answer remains one pass."""
    text = chains.compose_arm_action({"name": "ore-run-K7", "steps": 12})
    assert "ore-run-K7" in text
    assert "one pass" in text
    assert "12 steps" in text


def test_arm_action_renders_unknown_steps_as_a_question_mark():
    """Unknown is not zero -- the same honest-`?` rule
    `compose_relaunch_confirm_action` follows."""
    for bad in (None, -1, True, "12", 1.5):
        text = chains.compose_arm_action({"name": "x", "steps": bad})
        assert "? steps" in text, f"{bad!r} rendered as a definite count"


def test_arm_action_never_renders_a_blank_macro_name():
    for bad in (None, "", "   ", 7, {}):
        text = chains.compose_arm_action({"name": bad, "steps": 1})
        assert "Arm ?" in text
    assert "Arm ?" in chains.compose_arm_action(None)


def test_lines_mark_the_selected_row_with_canon_s_glyph():
    s = chains.ChainsSession()
    s.open(chains.playable_loops(TWO), "ok")
    lines = chains.compose_chain_lines(s)
    assert lines[1].startswith(chains.SELECTED_UNICODE)
    assert not lines[2].startswith(chains.SELECTED_UNICODE)
    s.move(1)
    lines = chains.compose_chain_lines(s)
    assert not lines[1].startswith(chains.SELECTED_UNICODE)
    assert lines[2].startswith(chains.SELECTED_UNICODE)


def test_ascii_terminals_lose_fidelity_but_not_meaning():
    s = chains.ChainsSession()
    s.open(chains.playable_loops(TWO), "ok")
    lines = chains.compose_chain_lines(s, unicode_ok=False)
    assert lines[1].startswith(chains.SELECTED_ASCII)
    assert chains.SELECTED_UNICODE not in "\n".join(lines)


def test_an_empty_store_renders_canon_s_empty_chain_placeholder():
    s = chains.ChainsSession()
    s.open([], "ok")
    body = "\n".join(chains.compose_chain_lines(s))
    assert chains.EMPTY_UNICODE in body
    assert chains.EMPTY_TEXT in body


@pytest.mark.parametrize("status", ["unreadable", "partial"])
def test_an_unreadable_store_is_never_rendered_as_empty(status):
    """The honesty rule this surface owes. `read_loop_store`'s contract makes
    `status` the field a caller must branch on before saying anything about
    how many loops exist; an empty list means "none taught" only under `ok`."""
    s = chains.ChainsSession()
    s.open([], status)
    body = "\n".join(chains.compose_chain_lines(s))
    assert chains.EMPTY_TEXT not in body, "claimed 'no trade loop yet' for an unread store"
    assert chains.UNKNOWN in body


def test_composers_never_raise_on_a_junk_session():
    for bogus in (None, 7, "session", object()):
        assert chains.compose_chain_lines(bogus)


def test_the_module_has_no_send_path():
    """Structural: nothing in this module can start a run. It imports no
    adapter and holds no socket -- the arm call lives in `app.py`, behind
    the confirm gate."""
    import inspect
    src = inspect.getsource(chains)
    assert "adapters" not in src
    assert "send_request" not in src
