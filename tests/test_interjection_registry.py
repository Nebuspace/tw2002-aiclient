"""Pins for the centralized settle interjection registry (tranche-10)."""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace

from tw2002_aiclient.session.interjection_registry import (
    INTERJECTION_IDS,
    match_interjection,
)


def test_registry_ids_are_the_closed_allow_list():
    assert INTERJECTION_IDS == frozenset(
        {
            "pause_key",
            "been_on_today",
            "show_todays_log",
            "clear_avoids",
            "inactivity_warning",
        }
    )


def test_match_interjection_ids_parity_with_frozenset():
    """Fail if match_interjection return ids drift from INTERJECTION_IDS.

    AST-scans ``_hit("…")`` / ``InterjectionHit("…")`` string literals inside
    ``match_interjection`` so a new branch cannot land without updating the
    frozenset (and the reverse: frozenset members need a return path).
    """
    src = inspect.getsource(match_interjection)
    tree = ast.parse(src)
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name not in {"_hit", "InterjectionHit"}:
            continue
        if not node.args:
            continue
        arg0 = node.args[0]
        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            found.add(arg0.value)
    assert found == set(INTERJECTION_IDS), (
        f"match_interjection ids {sorted(found)} != "
        f"INTERJECTION_IDS {sorted(INTERJECTION_IDS)}"
    )


def test_pause_key_absorbs_with_blank_enter():
    hit = match_interjection("pause_key", "[Pause]", "Command [TL=]")
    assert hit is not None
    assert hit.id == "pause_key"
    assert hit.response == ""


def test_show_todays_log_defaults_to_n():
    text = "Show today's log? (Y/N)\nCommand [TL=]"
    hit = match_interjection("unknown", text, "Command [TL=]")
    assert hit is not None
    assert hit.id == "show_todays_log"
    assert hit.response == "N"


def test_clear_avoids_respects_profile_flag():
    prompt = "Do you wish to clear some avoids? (Y/N)"
    hit_default = match_interjection(
        "unknown", prompt, prompt, profile=SimpleNamespace()
    )
    assert hit_default is not None and hit_default.response == "N"
    hit_clear = match_interjection(
        "unknown",
        prompt,
        prompt,
        profile=SimpleNamespace(clear_avoids_on_login=True),
    )
    assert hit_clear is not None and hit_clear.response == "Y"


def test_inactivity_scoped_to_option_block_not_stale_body():
    # Whole-grid would match the stale banner; option_block empty + clean
    # prompt must not absorb.
    text = "Critical inactivity warning!\n\nCommand [TL=99]"
    hit = match_interjection(
        "main_command", text, "Command [TL=99]", option_block=""
    )
    assert hit is None
    hit_live = match_interjection(
        "unknown",
        text,
        "?",
        option_block="Critical inactivity warning!",
    )
    assert hit_live is not None
    assert hit_live.id == "inactivity_warning"
    assert hit_live.response == ""


def test_unknown_screen_is_not_absorbed():
    assert (
        match_interjection(
            "unknown", "Something novel appeared", "Weird prompt?"
        )
        is None
    )
