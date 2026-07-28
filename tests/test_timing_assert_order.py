"""WO-TEST-TIMING-ASSERT-ORDER — no wall-clock assert before correctness.

A wall-clock / ``perf_counter`` / ``monotonic`` (or CPU ``rusage``) assert that
runs *before* a non-timing assert in the same test function masks defects:
under load the timing bound fails first, the correctness asserts never run,
and the failure reads as "the machine was busy" (K9 twin class, #134).

This meta-test walks every ``test_*.py`` under ``tests/`` and fails when that
order is inverted. Allowlist entries must carry a reason.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent

# (relative path from tests/, function name) → reason the WO permit stands.
# Empty by default — every current offender was reorderable.
ALLOWLIST: dict[tuple[str, str], str] = {}

_WALL_ATTRS = frozenset(
    {"perf_counter", "time", "monotonic", "process_time", "thread_time"}
)


def _is_wall_clock_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in _WALL_ATTRS:
        return True
    if isinstance(func, ast.Name) and func.id in _WALL_ATTRS | {"getrusage"}:
        return True
    return False


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _collect_timing_names(fn: ast.AST) -> set[str]:
    """Names bound to wall-clock / rusage measurements inside ``fn``."""
    timing: set[str] = set()

    def _note_assign(target: ast.AST, value: ast.AST) -> None:
        if isinstance(target, ast.Name):
            if any(_is_wall_clock_call(n) for n in ast.walk(value)):
                timing.add(target.id)
            if any(
                isinstance(n, ast.Attribute) and n.attr in ("ru_utime", "ru_stime")
                for n in ast.walk(value)
            ):
                timing.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                _note_assign(elt, value)

    for stmt in ast.walk(fn):
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                _note_assign(t, stmt.value)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            _note_assign(stmt.target, stmt.value)

    # Fixed-point: ``elapsed = now - t0`` where either side is already timing.
    changed = True
    while changed:
        changed = False
        for stmt in ast.walk(fn):
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            name = stmt.targets[0].id
            if name in timing:
                continue
            used = _names_in(stmt.value)
            if used & timing and isinstance(stmt.value, ast.BinOp):
                timing.add(name)
                changed = True
            elif used & timing and any(_is_wall_clock_call(n) for n in ast.walk(stmt.value)):
                timing.add(name)
                changed = True
    return timing


def _assert_is_timing(assert_node: ast.Assert, timing_names: set[str]) -> bool:
    if any(_is_wall_clock_call(n) for n in ast.walk(assert_node.test)):
        return True
    used = _names_in(assert_node.test)
    if used & timing_names:
        return True
    # Common canary names even if assignment shape was exotic.
    if used & {"cpu_s", "elapsed_wall", "wall_s"}:
        return True
    return False


def _violations_in_function(fn: ast.AST) -> list[int]:
    timing_names = _collect_timing_names(fn)
    asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
    asserts.sort(key=lambda a: (a.lineno or 0, a.col_offset or 0))
    seen_timing = False
    bad_lines: list[int] = []
    for a in asserts:
        is_timing = _assert_is_timing(a, timing_names)
        if seen_timing and not is_timing:
            bad_lines.append(a.lineno or 0)
        if is_timing:
            seen_timing = True
    return bad_lines


def _iter_test_functions(tree: ast.AST):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            yield node
        # class-based tests
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith(
                    "test_"
                ):
                    yield child


def test_no_wall_clock_assert_precedes_a_non_timing_assert():
    """Accept #1: structural — timing canaries may only run LAST."""
    offenders: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        rel = str(path.relative_to(TESTS_ROOT))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            offenders.append(f"{rel}: syntax error: {exc}")
            continue
        for fn in _iter_test_functions(tree):
            key = (rel, fn.name)
            if key in ALLOWLIST:
                continue
            bad = _violations_in_function(fn)
            for line in bad:
                offenders.append(
                    f"{rel}:{line} {fn.name}: non-timing assert after a "
                    f"wall-clock/rusage assert (reorder: correctness first, "
                    f"timing canary last)"
                )

    # Allowlist entries must stay justified — empty reason is a defect.
    for key, reason in ALLOWLIST.items():
        assert reason.strip(), f"ALLOWLIST {key} needs a non-empty reason"

    assert offenders == [], (
        "wall-clock/rusage assert precedes a non-timing assert:\n  "
        + "\n  ".join(offenders)
    )


def test_meta_detector_flags_timing_before_correctness():
    """Pin the detector itself: a synthetic function must be caught."""
    src = """
def test_bad_order():
    import time
    t0 = time.perf_counter()
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0
    assert True
"""
    tree = ast.parse(src)
    fn = tree.body[0]
    assert _violations_in_function(fn) == [7]


def test_meta_detector_accepts_correctness_then_timing():
    src = """
def test_good_order():
    import time
    t0 = time.perf_counter()
    elapsed = time.perf_counter() - t0
    assert True
    assert elapsed < 1.0
"""
    tree = ast.parse(src)
    fn = tree.body[0]
    assert _violations_in_function(fn) == []


def test_meta_detector_ignores_fake_elapsed_without_wall_clock():
    """Settle-style simulated ``elapsed`` is not a wall-clock canary."""
    src = """
def test_fake_clock():
    elapsed = 1.5  # simulated seconds, not perf_counter
    assert elapsed >= 1.0
    assert True
"""
    tree = ast.parse(src)
    fn = tree.body[0]
    assert _violations_in_function(fn) == []
