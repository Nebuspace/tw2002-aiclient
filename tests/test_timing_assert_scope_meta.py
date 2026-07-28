"""WO-TEST-TIMING-ASSERT-SCOPE-META — approximate mechanical scope gate.

Companion to the **prose** scope rule in ``tests/test_timing_assert_order.py``
(#185). Order is AST-enforced there; scope ("measure only the window the
message names") is not fully decidable statically. This module catches the
#184 shape that the order gate deliberately waves through:

* the test **spawns a child**, then
* asserts a **CPU / rusage** budget derived from that child's
  ``ru_utime``/``ru_stime`` (whole-life by construction),
* **without** a residual/setup split (self-stamp pattern from #184's fix).

Heuristic, not a full semantic scope detector. Documented false-negative
class: a whole-life pin that invents a novel name for the sum and never
mentions ``ru_utime``/``ru_stime`` in the same function (rare; prefer the
residual-stamp repair anyway). Documented false-positive class: a test that
both spawns and asserts whole-life CPU for a *named* whole-life claim —
allowlist with reason.

Refs: #185 scope prose · #184 residual-stamp exemplar · CC offer 19:43:52Z.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parent

# (relative path from tests/, function name) → reason the permit stands.
ALLOWLIST: dict[tuple[str, str], str] = {}

_SPAWN_NAME_HINTS = ("spawn", "Popen", "fork")

_RUSAGE_ATTRS = frozenset({"ru_utime", "ru_stime"})

_RESIDUAL_NAMES = frozenset(
    {"residual", "exit_cpu", "scoped_cpu", "cpu_after", "cpu_delta"}
)

_SETUP_BASELINE_NAMES = frozenset(
    {"setup", "stamp", "baseline", "cpu_before", "cpu_at_idle", "setup_cpu"}
)


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _function_spawns_child(fn: ast.AST) -> bool:
    """True if the function looks like it starts a subprocess/child."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name is None:
            continue
        if name in {"Popen", "fork"}:
            return True
        if any(h in name for h in _SPAWN_NAME_HINTS):
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {
            "Popen",
            "run",
            "call",
            "check_call",
            "check_output",
        }:
            # subprocess.run / subprocess.Popen
            if isinstance(node.func.value, ast.Name) and node.func.value.id in {
                "subprocess",
                "os",
            }:
                return True
    return False


def _rusage_sum_names(fn: ast.AST) -> set[str]:
    """Names bound to expressions that combine ``ru_utime`` / ``ru_stime``.

    Matches the #184 shape ``cpu_s = rusage.ru_utime + rusage.ru_stime`` and
    the helper-local ``total = rusage.ru_utime + rusage.ru_stime`` when that
    helper is inlined into a test (it usually is not — helpers are skipped).
    """
    names: set[str] = set()

    def _value_mentions_rusage(value: ast.AST) -> bool:
        for n in ast.walk(value):
            if isinstance(n, ast.Attribute) and n.attr in _RUSAGE_ATTRS:
                return True
        return False

    def _note_target(target: ast.AST, value: ast.AST) -> None:
        if not _value_mentions_rusage(value):
            return
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                if isinstance(elt, ast.Name):
                    names.add(elt.id)

    for stmt in ast.walk(fn):
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                _note_target(t, stmt.value)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            _note_target(stmt.target, stmt.value)
    return names


def _has_residual_split(fn: ast.AST) -> bool:
    """True if the function scopes CPU to a residual / baseline stamp.

    Matches #184's repair: assert ``residual``, or ``total - setup``, or a
    name in ``_RESIDUAL_NAMES`` bound from a subtraction involving a setup
    baseline.
    """
    for stmt in ast.walk(fn):
        if isinstance(stmt, ast.Assign):
            targets = []
            if len(stmt.targets) == 1:
                t = stmt.targets[0]
                if isinstance(t, ast.Name):
                    targets = [t.id]
                elif isinstance(t, (ast.Tuple, ast.List)):
                    targets = [e.id for e in t.elts if isinstance(e, ast.Name)]
            if any(n in _RESIDUAL_NAMES for n in targets):
                return True
            if isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, ast.Sub):
                if _names_in(stmt.value) & _SETUP_BASELINE_NAMES:
                    return True
        if isinstance(stmt, ast.Assert):
            used = _names_in(stmt.test)
            if used & _RESIDUAL_NAMES:
                return True
    return False


def _violations_in_function(fn: ast.AST) -> list[int]:
    """Line numbers of whole-life rusage/CPU asserts over a spawned child."""
    if not _function_spawns_child(fn):
        return []
    if _has_residual_split(fn):
        return []
    cpu_names = _rusage_sum_names(fn)
    if not cpu_names:
        return []
    bad: list[int] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assert):
            continue
        if _names_in(node.test) & cpu_names:
            bad.append(node.lineno or 0)
    return bad


def _iter_test_functions(tree: ast.AST):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            yield node
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and child.name.startswith("test_"):
                    yield child


def test_no_whole_life_rusage_cpu_assert_over_spawned_child():
    """Accept #1: approximate scope — spawn + whole-life CPU assert → red."""
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
            for line in _violations_in_function(fn):
                offenders.append(
                    f"{rel}:{line} {fn.name}: whole-life rusage/CPU assert over a "
                    f"test-spawned child (split with a residual stamp — see #184 / "
                    f"#185 scope prose — rather than charging startup as 'exiting')"
                )

    for key, reason in ALLOWLIST.items():
        assert reason.strip(), f"ALLOWLIST {key} needs a non-empty reason"

    assert offenders == [], (
        "whole-life CPU budget over spawned child:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Detector pins (synthetic) — #184 RED · residual GREEN · no false spawn
# ---------------------------------------------------------------------------


def test_meta_detector_flags_184_shaped_whole_life_pin():
    """Falsify: the original #184 pin shape must go RED."""
    src = """
def test_exits_cheaply():
    import subprocess, os, resource
    proc = subprocess.Popen(["true"])
    pid, status, rusage = os.wait4(proc.pid, 0)
    exited = True
    cpu_s = rusage.ru_utime + rusage.ru_stime
    assert exited
    assert cpu_s < 0.5, f"consumed {cpu_s:.3f}s CPU exiting -- looks like it spun first"
"""
    fn = ast.parse(src).body[0]
    bad = _violations_in_function(fn)
    assert bad, "184-shaped whole-life pin stayed green — detector vacuous"
    assert 9 in bad  # the cpu_s assert line in the synthetic source


def test_meta_detector_accepts_residual_stamped_pin():
    """#184 repair shape: assert residual after setup stamp → green."""
    src = """
def test_exits_cheaply_residual():
    import subprocess, os
    proc = subprocess.Popen(["true"])
    pid, status, rusage = os.wait4(proc.pid, 0)
    setup = 0.2  # as if read from child stamp
    total = rusage.ru_utime + rusage.ru_stime
    residual = total - setup
    assert True
    assert residual < 0.30
"""
    fn = ast.parse(src).body[0]
    assert _violations_in_function(fn) == []


def test_meta_detector_ignores_rusage_without_spawn():
    """No child → not the #184 class (order gate / other rules may still apply)."""
    src = """
def test_self_rusage():
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = r.ru_utime + r.ru_stime
    assert cpu_s < 10.0
"""
    fn = ast.parse(src).body[0]
    assert _violations_in_function(fn) == []


def test_order_gate_still_catches_inversion_on_184_shape():
    """Accept: genuine order inversion remains the order gate's job.

    Documented in #185: feeding the #184 pin to ``_violations_in_function``
    (order) returns ``[]``. This pin only checks that a *real* inversion is
    still caught there — we do not weaken that gate.
    """
    from tests.test_timing_assert_order import (
        _violations_in_function as order_violations,
    )

    src = """
def test_timing_before_correctness():
    import time
    t0 = time.perf_counter()
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0
    assert True
"""
    fn = ast.parse(src).body[0]
    assert order_violations(fn), "order gate went silent — do not ship this WO"
