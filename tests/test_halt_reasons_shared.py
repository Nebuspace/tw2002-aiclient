"""WO-HALT-QUALIFY-CONSOLIDATE -- one encoder, one parser, one separator.

`loops.player` and `session.sector_explore` both emit `<code>:<detail>` halt
reasons. They used to do it with independent three-line helpers: the player
built its separator from a constant, explore hardcoded `":"`. They agreed by
luck rather than by construction, so moving `QUALIFIER_SEP` would have left
explore behind while `halt_reason_code` split its reasons on the wrong
character -- and still returned something answer-shaped.

These pins are written as **identity** (`is`), not equality. Two separate
functions that happen to produce equal output would satisfy an equality
assertion while the duplication quietly returned; only `is` says "there is
exactly one of these".
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tw2002_aiclient import halt_reasons
from tw2002_aiclient.loops import player as p
from tw2002_aiclient.session import sector_explore as sx

_PRODUCT_ROOT = Path(__file__).resolve().parent.parent / "tw2002_aiclient"
_SHARED = _PRODUCT_ROOT / "halt_reasons.py"

#: Packages the shared primitive must never reach for. Importing any of them
#: turns it from a leaf into an edge in the graph it exists to keep flat.
_FORBIDDEN_ROOTS = ("session", "loops", "cockpit", "adapters")


# --- Accept 1 & 2: exactly one implementation -----------------------------


def test_both_producers_share_one_encoder() -> None:
    assert p._qualify is halt_reasons.qualify
    assert sx._qualify is halt_reasons.qualify


def test_there_is_one_parser() -> None:
    assert p.halt_reason_code is halt_reasons.halt_reason_code


def test_there_is_one_separator() -> None:
    assert p.QUALIFIER_SEP is halt_reasons.QUALIFIER_SEP


def test_neither_producer_defines_its_own_helper_any_more() -> None:
    """Identity above would still pass if a module defined a `def _qualify`
    and then rebound the name -- unlikely, but the source is cheap to ask."""
    for module in (_PRODUCT_ROOT / "loops" / "player.py",
                   _PRODUCT_ROOT / "session" / "sector_explore.py"):
        tree = ast.parse(module.read_text())
        defs = [n.name for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
                and n.name in {"_qualify", "qualify", "halt_reason_code"}]
        assert defs == [], f"{module.name} still defines {defs}"


# --- the constraint that makes the shared module possible at all ----------


def test_the_shared_module_is_dependency_neutral() -> None:
    """The old duplication existed to avoid an import edge. If this module
    grows one, the duplication was traded for the very thing it prevented."""
    tree = ast.parse(_SHARED.read_text())
    reached: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            reached += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            # level>0 is a relative import; module may be None for `from . import x`
            target = node.module or ""
            if node.level and any(
                target.startswith(r) or any(a.name.startswith(r) for a in node.names)
                for r in _FORBIDDEN_ROOTS
            ):
                reached.append(target or ".")
            elif not node.level:
                reached.append(target)
    offenders = [m for m in reached if m.split(".")[0] in _FORBIDDEN_ROOTS]
    assert offenders == [], f"halt_reasons must stay a leaf; reaches {offenders}"


def test_explore_does_not_reach_the_helper_through_the_loop_player() -> None:
    """Constraint: explore may import halt CONSTANTS from `loops.player`, but
    taking the helper from there would re-create the entanglement."""
    tree = ast.parse((_PRODUCT_ROOT / "session" / "sector_explore.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("loops.player"):
            names = {a.name for a in node.names}
            assert not (names & {"_qualify", "qualify", "halt_reason_code", "QUALIFIER_SEP"}), (
                f"sector_explore pulls the halt-reason helper from loops.player: {names}"
            )


# --- Accept 4: the compatibility surface callers rely on ------------------


def test_the_three_names_still_import_from_loops_player() -> None:
    from tw2002_aiclient.loops.player import (  # noqa: F401
        QUALIFIER_SEP,
        _qualify,
        halt_reason_code,
    )

    assert _qualify("a", "b") == "a:b"
    assert halt_reason_code("a:b") == "a"
    assert QUALIFIER_SEP == ":"


# --- Accept 3: the emitted shape did not move -----------------------------


@pytest.mark.parametrize(
    "code,detail,expected",
    [
        ("never_auto_action", "money_prompt", "never_auto_action:money_prompt"),
        ("halt_not_drivable", "fighter_encounter", "halt_not_drivable:fighter_encounter"),
        ("code", "", "code:"),
        ("", "detail", ":detail"),
        ("code", "a:b", "code:a:b"),
    ],
)
def test_the_qualified_shape_is_unchanged(code, detail, expected) -> None:
    assert halt_reasons.qualify(code, detail) == expected
    assert p._qualify(code, detail) == expected
    assert sx._qualify(code, detail) == expected


@pytest.mark.parametrize(
    "reason,expected",
    [
        ("never_auto_action:money_prompt", "never_auto_action"),
        ("never_auto_action", "never_auto_action"),
        ("a:b:c", "a"),          # FIRST separator only
        (":lead", ""),
        ("trail:", "trail"),
        ("", None),              # empty is not a code
        (None, None),            # non-string yields None, never a guess
        (123, None),
    ],
)
def test_the_parser_contract_is_unchanged(reason, expected) -> None:
    assert halt_reasons.halt_reason_code(reason) == expected
    assert p.halt_reason_code(reason) == expected


def test_round_trip_through_the_shared_pair() -> None:
    for code in ("never_auto_action", "halt_not_drivable"):
        for detail in ("money_prompt", "a:b", ""):
            assert halt_reasons.halt_reason_code(halt_reasons.qualify(code, detail)) == code


# --- the guard from #215 must still see both producers --------------------


def test_the_ast_comparison_guard_still_derives_both_qualifiable_codes() -> None:
    """#215's guard finds qualifiable codes by scanning `_qualify(<CODE>, ...)`
    call sites. Consolidation kept the local `_qualify` binding in both modules
    for exactly this reason -- renaming to `qualify` would have emptied the
    derived set and left that guard passing over everything."""
    import importlib.util

    guard_path = Path(__file__).resolve().parent / "test_halt_reason_comparison_guard.py"
    spec = importlib.util.spec_from_file_location("_halt_guard", guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)

    derived = guard._qualifiable_constants()
    assert "HALT_NEVER_AUTO_ACTION" in derived
    assert "HALT_NOT_DRIVABLE" in derived
