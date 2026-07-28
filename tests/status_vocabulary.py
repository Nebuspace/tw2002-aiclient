"""Static vocabulary of the cockpit ``status`` dict: who reads it, who writes it.

Test-only helper for ``tests/test_status_vocabulary_guard.py``. It exists because
the gap it measures is **invisible to every other kind of test**: a panel that
reads ``status["turns_left"]`` when nothing writes it renders an honest ``?`` and
passes its own suite forever, because the suite supplies what reality does not.
Only comparing the two sets can see it.

**The two scan traps, both hit for real while scoping this (2026-07-28).**

*Named constants (false NEGATIVE).* ``chain_status.py`` writes the field as
``merged[HOPS_KEY] = ...``. A scan matching only string-literal subscripts reports
"no writer" for a producer that shipped an hour earlier. Module-level
``NAME = "literal"`` bindings are therefore resolved.

*Label tables (false POSITIVE).* ``goals.py``'s ``_LABELS`` and ``hud.py``'s
``_FIELD_LABELS`` are dict literals keyed by field name — display strings, not
producers. A scan counting dict-literal keys anywhere reports ``credits`` as
supplied when nothing supplies it. Producers are therefore recognised only by the
shapes that actually *augment a dict*: subscript assignment and ``.update({...})``.
A bare dict literal bound to a name is never a producer here. The one exception is
``_status_response``, scanned **by function name** precisely because building the
response dict as a literal is what it does.

**Blind spots fail in the safe direction.** If this scanner cannot see some future
producer's write shape, that field keeps computing as starved; the seat wiring it
must then delete its allowlist entry, the exact-set assertion goes **red**, and
they are forced to either teach the scanner or use a recognised shape. A missed
producer cannot silently pass — it can only block.
"""

from __future__ import annotations

import ast
import pathlib

__all__ = ["consumed_keys", "emitted_keys", "starved_keys", "repo_root"]

# The dict variable panels receive their status snapshot as.
_STATUS_VAR = "status"

# The whole consumer surface: every cockpit panel composer, plus `screens.py`,
# which reads `connected`/`idle_ms` off the same snapshot before handing it on.
_CONSUMER_GLOBS = ("tw2002_aiclient/cockpit/*.py",)
_CONSUMER_FILES = ("tw2002_aiclient/screens.py",)

# The daemon's answer to the `status` verb — scanned by name, see module docstring.
_PRODUCER_FILE = "tw2002_aiclient/session/protocol.py"
_PRODUCER_FN = "_status_response"


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def _parse(path: pathlib.Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def _module_str_consts(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` bindings, so constant-keyed writes are
    visible (the false-negative trap)."""
    out: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            out[node.targets[0].id] = node.value.value
    return out


def _key_of(node: ast.expr, consts: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


def _consumer_paths(root: pathlib.Path) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for glob in _CONSUMER_GLOBS:
        paths.extend(sorted(root.glob(glob)))
    paths.extend(root / f for f in _CONSUMER_FILES)
    return [p for p in paths if p.exists()]


def consumed_keys(root: pathlib.Path | None = None) -> dict[str, set[str]]:
    """``{key: {file, …}}`` for every key read off a dict named ``status``.

    Both read shapes count — ``status.get("k")`` and ``status["k"]`` — because
    both are used across the panels and a scan seeing one is a scan with a hole.
    """
    root = root or repo_root()
    found: dict[str, set[str]] = {}
    for path in _consumer_paths(root):
        tree = _parse(path)
        if tree is None:
            continue
        name = str(path.relative_to(root))
        for node in ast.walk(tree):
            key = None
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == _STATUS_VAR
                and node.args
            ):
                key = _key_of(node.args[0], {})
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id == _STATUS_VAR
            ):
                key = _key_of(node.slice, {})
            if key:
                found.setdefault(key, set()).add(name)
    return found


def emitted_keys(root: pathlib.Path | None = None) -> dict[str, set[str]]:
    """``{key: {"file:line", …}}`` for every key some product code WRITES.

    Two recognised producer kinds, and nothing else (see the module docstring on
    why dict literals are excluded everywhere but one place):

    1. the daemon's ``_status_response``, scanned by function name — dict
       literals and subscript assignment both count *inside it*;
    2. client-side overlays anywhere in the package, recognised by
       ``d[key] = …`` or ``d.update({key: …})``, with constants resolved.
    """
    root = root or repo_root()
    found: dict[str, set[str]] = {}

    def record(key: str, path: pathlib.Path, lineno: int) -> None:
        found.setdefault(key, set()).add(f"{path.relative_to(root)}:{lineno}")

    producer = root / _PRODUCER_FILE
    tree = _parse(producer)
    if tree is not None:
        consts = _module_str_consts(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef) and node.name == _PRODUCER_FN):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Dict):
                    for k in inner.keys:
                        key = _key_of(k, consts) if k is not None else None
                        if key:
                            record(key, producer, inner.lineno)
                if isinstance(inner, ast.Assign):
                    for tgt in inner.targets:
                        if isinstance(tgt, ast.Subscript):
                            key = _key_of(tgt.slice, consts)
                            if key:
                                record(key, producer, tgt.lineno)

    for path in sorted((root / "tw2002_aiclient").rglob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        consts = _module_str_consts(tree)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Only dicts the function actually HANDS BACK count as producing
            # status. Without this the scan credits every `cache["credits"] = x`
            # anywhere in the package, and an unrelated dict sharing a field
            # name would mark that field supplied -- silently retiring a real
            # gap. This is the one over-broad direction that fails UNSAFE, so
            # it is narrowed by dataflow rather than by naming convention:
            # an overlay is `merged[KEY] = v; ...; return merged`.
            returned = {
                r.value.id
                for r in ast.walk(fn)
                if isinstance(r, ast.Return) and isinstance(r.value, ast.Name)
            }
            if not returned:
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Assign):
                    for tgt in node.targets:
                        if (
                            isinstance(tgt, ast.Subscript)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id in returned
                        ):
                            key = _key_of(tgt.slice, consts)
                            if key:
                                record(key, path, tgt.lineno)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "update"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in returned
                    and node.args
                    and isinstance(node.args[0], ast.Dict)
                ):
                    for k in node.args[0].keys:
                        key = _key_of(k, consts) if k is not None else None
                        if key:
                            record(key, path, node.lineno)
    return found


def starved_keys(root: pathlib.Path | None = None) -> dict[str, set[str]]:
    """Keys a panel reads that no product code writes — ``{key: {reader, …}}``."""
    root = root or repo_root()
    consumed = consumed_keys(root)
    emitted = set(emitted_keys(root))
    return {k: v for k, v in consumed.items() if k not in emitted}
