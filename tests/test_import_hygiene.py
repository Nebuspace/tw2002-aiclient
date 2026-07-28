"""Package-wide import hygiene — no network, no product import at module scope.

WO-EXPLORE-TWCLIENT-FORMATIONS-LANDMINE. `tw2002_aiclient/explore.py` carried
`from twclient.formations import catalog_world` for weeks after ADR-001 deleted
the whole `twclient` package. It raised `ModuleNotFoundError` on the first call
and nothing caught it, because three things lined up:

1. the import was **function-level**, so importing the module stayed clean;
2. `tests/test_formations.py` is `--ignore`d in `pytest.ini`;
3. the one collected test that called it opened with an unconditional
   `pytest.skip(...)`, so it was counted as a skip and its body never ran.

Every layer of "is it covered?" answered yes-ish. This module asks the only
question that could have caught it: **does every import in the package name a
module that actually exists?**
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib

import pytest

PKG = pathlib.Path(__file__).resolve().parent.parent / "tw2002_aiclient"

_IMPORT_ERROR_NAMES = {"ImportError", "ModuleNotFoundError"}


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    """A bare `except:` counts — it swallows ImportError too."""
    if handler.type is None:
        return True
    nodes = (
        handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    )
    return any(isinstance(n, ast.Name) and n.id in _IMPORT_ERROR_NAMES for n in nodes)


def _guarded_imports(tree: ast.AST) -> set[int]:
    """`id()`s of import nodes inside a try/except that catches ImportError.

    These are the canonical optional-dependency fallback --
    `try: import tomllib / except ImportError: import tomli as tomllib` --
    and are deliberately NOT landmines: the failure is handled by design.
    A checker that cannot tell them apart reports two false positives on
    this very package (`session/credentials.py`, `session/protocol.py`) and
    is therefore useless as a gate.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(_handler_catches_import_error(h) for h in node.handlers):
            continue
        for branch in [node.body, *[h.body for h in node.handlers]]:
            for stmt in branch:
                for sub in ast.walk(stmt):
                    if isinstance(sub, (ast.Import, ast.ImportFrom)):
                        guarded.add(id(sub))
    return guarded


def _unresolvable_imports(source: str, label: str) -> list[str]:
    """Every absolute import in `source` whose TOP-LEVEL package does not
    resolve. Top-level only, deliberately: it is enough to catch a deleted
    package, and it avoids importing our own submodules as a side effect of
    the check. Relative imports (`level > 0`) are intra-package and are
    already exercised by importing the package at all."""
    tree = ast.parse(source)
    guarded = _guarded_imports(tree)
    bad: list[str] = []
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.Import):
            targets = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets = [node.module]
        else:
            continue
        for target in targets:
            top = target.split(".")[0]
            try:
                found = importlib.util.find_spec(top) is not None
            except (ImportError, ModuleNotFoundError, ValueError):
                found = False
            if not found:
                bad.append(f"{label}:{node.lineno} -> {target} (top-level '{top}')")
    return bad


def test_no_product_module_imports_an_unresolvable_target():
    """The landmine class guard. A function-level import of a deleted
    package is invisible to import-time checks, to an `--ignore`d test file,
    and to a skipped test -- but not to this."""
    bad: list[str] = []
    for path in sorted(PKG.rglob("*.py")):
        bad.extend(
            _unresolvable_imports(path.read_text(), str(path.relative_to(PKG.parent)))
        )
    assert not bad, "unresolvable import(s) — armed ModuleNotFoundError:\n  " + "\n  ".join(bad)


# -- the guard's own vacuity pins: a check that cannot fail is not a check ----


def test_guard_catches_a_bare_unresolvable_import():
    src = "from twclient.formations import catalog_world\n"
    assert _unresolvable_imports(src, "synthetic") != []


def test_guard_catches_a_FUNCTION_LEVEL_unresolvable_import():
    """The exact shape that hid: nested in a body, not at module scope."""
    src = "def f():\n    from twclient.formations import catalog_world\n    return 1\n"
    assert _unresolvable_imports(src, "synthetic") != []


@pytest.mark.parametrize(
    "src",
    [
        "try:\n    import tomllib\nexcept ImportError:\n    import tomli as tomllib\n",
        "try:\n    import tomllib\nexcept (ImportError, OSError):\n    import tomli\n",
        "try:\n    import tomllib\nexcept ModuleNotFoundError:\n    import tomli\n",
        "try:\n    import tomllib\nexcept:\n    import tomli\n",
    ],
)
def test_guard_does_NOT_flag_a_guarded_optional_dependency(src):
    """Fail-open on the deliberate fallback. If this ever goes red the guard
    starts demanding regressions in correct code -- the same trap that made
    `test_dead_terminal_spin.py`'s rusage asserts look like a defect class."""
    assert _unresolvable_imports(src, "synthetic") == []


def test_guard_does_not_flag_a_resolvable_import():
    assert _unresolvable_imports("import json\nfrom pathlib import Path\n", "s") == []
