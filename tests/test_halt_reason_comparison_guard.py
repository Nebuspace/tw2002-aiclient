"""WO-HALT-REASON-NE-SWEEP -- comparisons against qualifiable halt codes.

A halt reason that gained a qualified form (``never_auto_action`` becoming
``never_auto_action:money_prompt``) breaks its assertions **asymmetrically**:

  * every ``== HALT_NEVER_AUTO_ACTION`` turns red at once -- loud, found, fixed
  * every ``!= HALT_NEVER_AUTO_ACTION`` turns *trivially true* -- silent

The negative ones stop excluding what they name and nothing says so. They live
wherever anyone ever excluded the bare value, which is generally NOT the module
being qualified, so the loud red positives are a false signal of "found them
all". #214 fixed the one live instance; this guard is what stops the next one.

The sweep itself found a clean tree (see the WO STATUS): the value here is
enforcement, not remediation. A hand-sweep fixes today and regrows tomorrow.

**The qualifiable set is derived from the product, never hardcoded.** If it were
a literal list, the next code to gain ``_qualify`` would simply not be covered
and this guard would keep passing -- the exact failure it exists to prevent.
`test_the_derivation_is_not_vacuous` is the control on that derivation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tw2002_aiclient.loops import player as p
from tw2002_aiclient.session import sector_explore as sx

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRODUCT_ROOT = _REPO_ROOT / "tw2002_aiclient"
_TESTS_ROOT = _REPO_ROOT / "tests"

#: The parser every comparison against a qualifiable code must route through.
#: One name, because a second parser is how the two halves drift apart.
_PARSER = "halt_reason_code"


def _name_of(node: ast.AST) -> str | None:
    """The bare identifier behind ``X``, ``mod.X``, or a plain string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _python_sources(root: Path) -> list[Path]:
    return sorted(q for q in root.rglob("*.py") if "__pycache__" not in q.parts)


def _qualifiable_constants() -> set[str]:
    """Constant names the product actually passes to ``_qualify``.

    Derived by walking the product for ``_qualify(<CODE>, ...)`` call sites, so
    a newly-qualified code is covered the moment it is written -- no list to
    forget to update.
    """
    found: set[str] = set()
    for path in _python_sources(_PRODUCT_ROOT):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _name_of(node.func) != "_qualify" or not node.args:
                continue
            name = _name_of(node.args[0])
            if name:
                found.add(name)
    return found


def _is_static_side(node: ast.AST, qualifiable: set[str]) -> bool:
    """True when this side is a *constant*, not a runtime reason value.

    ``HALT_A != HALT_B`` and ``HALT_A == "never_auto_action"`` compare two fixed
    things -- qualification cannot weaken them, and they are how the constants'
    own spellings get pinned. The hazard is strictly a runtime reason measured
    against a bare code.
    """
    if isinstance(node, ast.Constant):
        return True
    name = _name_of(node)
    return bool(name and (name.startswith("HALT_") or name in qualifiable))


def _is_guarded(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _name_of(node.func) == _PARSER


def _bare_comparisons(paths: list[Path], qualifiable: set[str]) -> list[str]:
    """Sites comparing a runtime value against a bare qualifiable code."""
    literals = {getattr(p, n, None) for n in qualifiable} | {
        getattr(sx, n, None) for n in qualifiable
    }
    literals.discard(None)
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for op, right in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.Eq, ast.NotEq)):
                    continue
                for side, other in ((right, node.left), (node.left, right)):
                    name = _name_of(side)
                    if name not in qualifiable and name not in literals:
                        continue
                    # No carve-out is needed for an exact qualified literal
                    # (`== "never_auto_action:money_prompt"`): it is not equal
                    # to any bare code, so it never matches the filter above.
                    # One was written here and the mutation matrix proved it
                    # unreachable -- a second layer saying what the first
                    # already said, which no test could ever have exercised.
                    if _is_static_side(other, qualifiable) or _is_guarded(other):
                        continue
                    # Repo files report repo-relative (readable in a failure);
                    # a control's tmp file is outside the root and reports as-is.
                    rel = (
                        path.relative_to(_REPO_ROOT)
                        if path.is_relative_to(_REPO_ROOT)
                        else path
                    )
                    offenders.append(f"{rel}:{node.lineno}")
                    break
    return sorted(set(offenders))


# --- the guard ------------------------------------------------------------


def test_no_runtime_reason_is_compared_against_a_bare_qualifiable_code() -> None:
    """The enforcement. A new bare `!=` against a qualified code fails here.

    Fix by comparing the parsed base -- `halt_reason_code(reason) != CODE` --
    or by asserting the exact qualified string, which is stronger still.
    """
    qualifiable = _qualifiable_constants()
    offenders = _bare_comparisons(
        _python_sources(_TESTS_ROOT) + _python_sources(_PRODUCT_ROOT), qualifiable
    )
    assert offenders == [], (
        "these compare a runtime halt reason against a bare code that can carry "
        f"`:detail`, so they no longer exclude what they name: {offenders}"
    )


# --- controls: a guard nobody can prove fires is not a guard ---------------


def test_the_derivation_is_not_vacuous() -> None:
    """If `_qualify` call-site discovery breaks, the guard above passes ALL.

    An empty derived set and a genuinely clean tree are indistinguishable from
    the assertion's point of view, so the derivation is pinned separately.
    """
    qualifiable = _qualifiable_constants()
    assert "HALT_NEVER_AUTO_ACTION" in qualifiable
    assert "HALT_NOT_DRIVABLE" in qualifiable


@pytest.mark.parametrize(
    "source",
    [
        "assert report.reason != HALT_NEVER_AUTO_ACTION\n",
        "assert report.reason == HALT_NOT_DRIVABLE\n",
        'assert result.reason != "never_auto_action"\n',
        "assert sx.HALT_NOT_DRIVABLE != run().reason\n",
    ],
)
def test_the_guard_actually_fires_on_a_bare_comparison(tmp_path, source) -> None:
    """Positive control -- the offending shape is *detected*, not merely absent.

    An empty result is the guard's own pass condition, so "no offenders" has to
    be shown to mean a clean tree rather than a scanner that finds nothing.
    Covers both operators, the module-qualified spelling, and the literal.
    """
    bad = tmp_path / "offender.py"
    bad.write_text(source)
    assert _bare_comparisons([bad], _qualifiable_constants()) == [f"{bad}:1"]


def test_the_guard_accepts_the_two_honest_forms(tmp_path) -> None:
    """Negative control -- a guard that flags everything would also be green."""
    ok = tmp_path / "fine.py"
    ok.write_text(
        "assert halt_reason_code(report.reason) != HALT_NEVER_AUTO_ACTION\n"
        'assert report.reason == "never_auto_action:money_prompt"\n'
        "assert HALT_NOT_DRIVABLE != HALT_UNRECOGNIZED_SCREEN\n"
        'assert HALT_NEVER_AUTO_ACTION == "never_auto_action"\n'
    )
    assert _bare_comparisons([ok], _qualifiable_constants()) == []


# --- the twin producers must not drift ------------------------------------


def test_the_two_qualify_helpers_produce_the_same_shape() -> None:
    """`player._qualify` and `sector_explore._qualify` are independent twins.

    Player builds its separator from `QUALIFIER_SEP`; explore hardcodes `":"`.
    They agree today, and nothing made them agree -- so a change to
    `QUALIFIER_SEP` would move the player and leave explore behind, and
    `halt_reason_code` would then split explore's reasons on the wrong
    character while still returning something that looks like an answer.
    """
    assert p._qualify("code", "detail") == sx._qualify("code", "detail")


def test_the_parser_round_trips_both_producers() -> None:
    """The direction that actually matters: whatever either side emits, the one
    parser must recover the bare code from it."""
    for qualify in (p._qualify, sx._qualify):
        assert p.halt_reason_code(qualify(p.HALT_NEVER_AUTO_ACTION, "x")) == (
            p.HALT_NEVER_AUTO_ACTION
        )
        assert p.halt_reason_code(qualify(sx.HALT_NOT_DRIVABLE, "y")) == (
            sx.HALT_NOT_DRIVABLE
        )


@pytest.mark.parametrize("detail", ["money_prompt", "fighter_encounter", "a:b"])
def test_a_qualified_reason_never_equals_its_bare_code(detail: str) -> None:
    """The property the whole sweep rests on, stated once as an executable fact
    rather than left implicit in each site's comment.

    Written against the *parsed* base rather than the bare constant on purpose:
    the obvious spelling (`qualified != HALT_NEVER_AUTO_ACTION`) is the very
    shape the guard above forbids, and the guard flagged this line on its first
    run. Detection is unchanged -- a `_qualify` that regressed to returning the
    code untouched still fails here -- but the assertion cannot itself rot if a
    third element is ever added to the reason format.
    """
    qualified = p._qualify(p.HALT_NEVER_AUTO_ACTION, detail)
    assert qualified != p.halt_reason_code(qualified)
    assert p.halt_reason_code(qualified) == p.HALT_NEVER_AUTO_ACTION
