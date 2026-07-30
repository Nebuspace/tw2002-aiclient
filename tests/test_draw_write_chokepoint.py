"""The single curses-write chokepoint, swept structurally across the product.

`cockpit/draw.py::safe_write` calls itself "THE ONE coordinate-write
primitive for every screen family". `tests/test_safe_addstr_choke.py`
already proves that primitive is *hardened* and that `screens.py` delegates
onto it. What neither file establishes is that it is still the ONLY one --
those pins name the call sites that existed when they were written, so a
module added tomorrow may write `win.addstr(...)` directly and every suite
stays green. Remediation without enforcement regrows; this is the tripwire.

# Why this is a safety pin and not tidiness

`safe_write` is not just the cell-width clip. It is `_sanitize_controls`,
which collapses every C0 (`\\x00-\\x1f`) and C1 (`\\x7f-\\x9f`) control to a
space. From `draw.py`'s own docstring, a `\\n` reaching `addstr` "would
otherwise move the real terminal cursor when addstr prints it, escaping
whatever box the caller thought it was confined to."

The text on that path is **bytes from a remote game server** -- content the
operator did not author and this app does not control. A bypass is not a
cosmetic regression, it is an unsanitized remote-content write to the
terminal. That is what earns a structural guard rather than a comment.

# Scope of the reflection leg, stated honestly

`test_menu_crawl_chokepoint.py` -- the house idiom this file mirrors -- can
ban reflection outright because the `menu` package is small. The product
tree is ~97 modules with many ordinary reflection-builtin calls, nearly
all of them correct. A blanket ban here would be noise, and a safety
scanner that cries wolf is a safety scanner someone switches off.

So this leg is deliberately narrow: reflection is flagged only when the
attribute being reached **resolves to a curses write name** -- as a literal,
or through a module-level string constant, since indirection is the whole
evasion surface. `test_the_scanner_sees_through_a_module_constant` proves
the constant hop is actually followed.

**What this does NOT catch, stated rather than implied:** an attribute name
assembled at runtime (`getattr(win, "add" + "str")`) is invisible to any
literal-node scan, here and in the house idiom alike. The guard is a
tripwire against drift and honest mistakes, not a sandbox against an author
deliberately hiding a write. Anyone who wants that should say so and get a
different mechanism.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tw2002_aiclient import cockpit

_PRODUCT_ROOT = Path(cockpit.__file__).resolve().parent.parent

# Every curses window method that puts glyphs on the screen. `addstr` is the
# only one in use; the rest are here because the guard must cover the ways a
# future author could write to a window, not merely the way today's does.
_WRITE_ATTRS = frozenset({
    "addstr", "addnstr", "insstr", "insnstr", "addch", "insch",
})

# The one sanctioned site: the primitive that sanitizes and cell-clips.
_CHOKE_FILE = "draw.py"
_CHOKE_FUNC = "safe_write"

_REFLECTION_BUILTINS = frozenset({"getattr", "setattr"})

# A floor, not the exact count -- an exact count would turn every new module
# into a failure of THIS test. Its job is only to prove the walk found the
# tree at all: `Path.rglob` returns an empty iterator just as happily for a
# wrong root as for a clean one, and every assertion below passes vacuously
# on zero files.
_MIN_PRODUCT_FILES = 50


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` bindings, so the scanner can see
    through a named constant the way it sees through an import alias."""
    consts: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = node.value.value
    return consts


def _enclosing_functions(tree: ast.Module) -> dict[int, str]:
    """Map each node to its enclosing function name. A call's SHAPE is not
    enough -- the same shape in a different function is a different fact,
    and 'the write moved out of safe_write' is exactly the drift to catch."""
    enclosing: dict[int, str] = {}
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(func):
                enclosing.setdefault(id(child), func.name)
    return enclosing


def _scan_source(source: str, filename: str) -> list[tuple[str, tuple[str, str | None, int]]]:
    """Return every curses-write reach in *source*, tagged by kind and site."""
    tree = ast.parse(source, filename=filename)
    consts = _module_string_constants(tree)
    enclosing = _enclosing_functions(tree)

    findings: list[tuple[str, tuple[str, str | None, int]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        where = (filename, enclosing.get(id(node)), node.lineno)
        fn = node.func

        if isinstance(fn, ast.Attribute) and fn.attr in _WRITE_ATTRS:
            findings.append(("raw_write", where))
            continue

        if isinstance(fn, ast.Name) and fn.id in _REFLECTION_BUILTINS and len(node.args) >= 2:
            attr = node.args[1]
            if isinstance(attr, ast.Constant) and isinstance(attr.value, str):
                name = attr.value
            elif isinstance(attr, ast.Name):
                name = consts.get(attr.id)
            else:
                name = None  # computed at runtime -- see the module docstring
            if name in _WRITE_ATTRS:
                findings.append(("reflected_write", where))
    return findings


def _scan_product_tree() -> tuple[list[tuple[str, tuple[str, str | None, int]]], int]:
    findings = []
    files = sorted(_PRODUCT_ROOT.rglob("*.py"))
    for path in files:
        rel = path.relative_to(_PRODUCT_ROOT)
        findings.extend(_scan_source(path.read_text(encoding="utf-8"), str(rel)))
    return findings, len(files)


# -- the sweep actually swept something ----------------------------------------


def test_the_sweep_reaches_the_product_tree() -> None:
    """Every assertion below is of the form "no bad thing found". Each one
    passes perfectly on an empty file list, so the population is pinned
    separately -- otherwise a wrong root turns this whole file green and
    silent, which is worse than not having it."""
    _findings, count = _scan_product_tree()
    assert count >= _MIN_PRODUCT_FILES, f"only {count} product modules scanned"


def test_the_scanner_finds_the_real_write_that_is_known_to_exist() -> None:
    """The positive control. `safe_write` demonstrably calls `addstr`, so a
    scanner reporting zero writes is broken, not clean -- and 'zero' is
    exactly what a silently-failing scan returns."""
    findings, _count = _scan_product_tree()
    assert [k for k, _ in findings] == ["raw_write"], findings


# -- the structural sweep ------------------------------------------------------


def test_exactly_one_curses_write_call_site_in_the_product_tree() -> None:
    """The tripwire. A new module writing to a window directly lands here."""
    findings, _count = _scan_product_tree()
    writes = [where for kind, where in findings if kind == "raw_write"]
    assert len(writes) == 1, f"expected one curses write path, found: {writes}"


def test_the_one_write_site_is_inside_the_function_that_sanitizes() -> None:
    """Counting to one is not enough: the write must live in the function
    that sanitizes and cell-clips. Moved one function over inside the same
    file, the count still reads 1 while the guarantee is gone."""
    findings, _count = _scan_product_tree()
    (filename, func, _lineno) = [w for k, w in findings if k == "raw_write"][0]
    assert Path(filename).name == _CHOKE_FILE, filename
    assert func == _CHOKE_FUNC, f"the curses write moved out of {_CHOKE_FUNC}: {func}"


def test_no_module_reaches_a_curses_write_by_reflection() -> None:
    """`getattr(win, "addstr")(...)` is a write that a name-based scan walks
    straight past unless it is looked for on purpose."""
    findings, _count = _scan_product_tree()
    reflected = [where for kind, where in findings if kind == "reflected_write"]
    assert reflected == [], f"a curses write reached by reflection: {reflected}"


# -- the scanner is not vacuous ------------------------------------------------
#
# The load-bearing half. A guard that cannot see a violation certifies
# nothing, and every one of these was written to fail first.


@pytest.mark.parametrize(
    "source, expected",
    [
        pytest.param(
            "def paint(win):\n    win.addstr(0, 0, 'hi')\n",
            "raw_write",
            id="a-new-module-writing-directly",
        ),
        pytest.param(
            "def paint(win):\n    win.addnstr(0, 0, 'hi', 4)\n",
            "raw_write",
            id="a-write-method-nobody-uses-today",
        ),
        pytest.param(
            "def paint(win):\n    win.addch(0, 0, 'x')\n",
            "raw_write",
            id="single-character-write",
        ),
        pytest.param(
            "def paint(win):\n    getattr(win, 'addstr')(0, 0, 'hi')\n",
            "reflected_write",
            id="reflection-with-a-literal-name",
        ),
        pytest.param(
            "_M = 'addstr'\n\n\ndef paint(win):\n    getattr(win, _M)(0, 0, 'hi')\n",
            "reflected_write",
            id="reflection-through-a-module-constant",
        ),
    ],
)
def test_the_scanner_catches_each_evasion(source: str, expected: str) -> None:
    kinds = [kind for kind, _where in _scan_source(source, "invented.py")]
    assert expected in kinds, f"scanner blind to {expected}: {kinds}"


def test_the_scanner_sees_through_a_module_constant() -> None:
    """Pinned on its own, not only as a parametrize row: the constant hop is
    the one piece of machinery here that could quietly stop working while
    every literal case kept passing."""
    literal = _scan_source("def p(w):\n    getattr(w, 'addstr')()\n", "a.py")
    viaconst = _scan_source("_N = 'addstr'\n\n\ndef p(w):\n    getattr(w, _N)()\n", "b.py")
    assert [k for k, _ in literal] == ["reflected_write"]
    assert [k for k, _ in viaconst] == ["reflected_write"], "constant resolution is dead"


def test_the_scanner_does_not_fire_on_ordinary_reflection() -> None:
    """The false-positive guard, and the reason the reflection leg is scoped
    to write names instead of banned outright. The product tree makes many
    ordinary reflection calls; a scanner that flagged them would be turned
    off within the week and the real signal would go with it."""
    benign = "def p(o):\n    return getattr(o, 'name', None) or getattr(o, 'handle')\n"
    assert _scan_source(benign, "benign.py") == []


def test_the_scanner_reports_where_not_merely_that() -> None:
    """A failure that cannot say which file and line is a failure someone
    reruns rather than fixes."""
    findings = _scan_source("def paint(win):\n    win.addstr(0, 0, 'hi')\n", "somewhere.py")
    (filename, func, lineno) = findings[0][1]
    assert (filename, func, lineno) == ("somewhere.py", "paint", 2)
