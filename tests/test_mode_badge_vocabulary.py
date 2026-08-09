"""WO-P5-060 lane C -- structural proof that no retired mode-badge
vocabulary (``AI-PILOT`` / ``ai_pilot`` / ``AUTO-LOOP``) exists anywhere in
the reborn product tree.

Canon: ``canon/surfaces/mode-line-and-teach-controls.md:21-38`` rules the
mode line a **dual** (App XOR Human) -- the AI is never a mode. The
"Code divergence" section (``:363-367``) names the archive's badge table
(``archive/pre-rebirth-2026-07-23/code/twclient/spectate_layout.py:2717``)
as carrying the legacy ``ai_pilot -> "AI-PILOT"`` mapping the reborn App
chip retires, and ``:184-186`` retires ``AUTO-LOOP`` in the same breath
(the as-built App holder is described there as "two badges -- ``AUTO-LOOP``
at tone ``ok``/green and the legacy ``AI-PILOT`` at tone ``info``/cyan" --
both are pre-reborn framing this gate bans from the product tree).

Scope: this scanner walks every ``.py`` file under ``tw2002_aiclient/``
only -- never ``archive/`` (the archive is reference material and is
EXPECTED to still carry the retired vocabulary; that's the whole point of
calling it legacy) and never ``tests/`` (this file's own docstring, and
every other test file's, is allowed to discuss the ban by name).

Detection rule: an ``ast.Constant`` node whose value is a ``str`` and
which contains (via a plain, case-sensitive Python ``in`` substring check)
one of the three literal terms ``"AI-PILOT"``, ``"ai_pilot"``, or
``"AUTO-LOOP"`` -- EXCLUDING any such Constant that IS a docstring (the
first ``Expr`` statement's ``Constant`` in a ``Module``/``ClassDef``/
``FunctionDef``/``AsyncFunctionDef`` body). Docstrings citing the ban by
name (this module's own docstring, and the ``D5: no ``ai_pilot``/
imperative-mood text anywhere`` convention already stamped across several
``cockpit/*.py`` modules) are the mechanism by which the ban is
documented; they are not the violation. A same-shaped string that is NOT
syntactically a docstring -- e.g. a second statement in a function body
that happens to be a bare string literal, or any string assigned to a
name, dict key/value, f-string fragment, or call argument -- is a real
badge/vocabulary string and DOES fire, no matter where it sits.

Comments are invisible to Python's ``ast`` module entirely (they never
become nodes), so no exclusion logic is needed for them -- this scanner
simply cannot see them, which is the honest and sufficient posture for a
static AST gate.

Disclosed residual (same family as ``tests/test_spectate_no_send.py``'s
own dynamic-reflection disclosure): a string ASSEMBLED at runtime, e.g.
``"AI-" + "PILOT"`` or ``"".join(["AI", "-", "PILOT"])``, produces no
single ``ast.Constant`` containing the full banned literal and is outside
the reach of any static content scan. This is a known, accepted gap, not
a defect in the scanner -- the same way a fully dynamic ``getattr(obj,
name_var)`` is outside the reach of the sibling send-capability guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PRODUCT_ROOT = Path(__file__).resolve().parent.parent / "tw2002_aiclient"

_BANNED_TERMS = ("AI-PILOT", "ai_pilot", "AUTO-LOOP")

# Positive-control identity for the tree walk (WO-BADGE-SCAN-IDENTITY-FLOOR).
# Cardinality (`len > 10`) stays green if an entire subpackage drops out of
# the walk — one named file per package the gate claims to cover does not.
_SCAN_IDENTITY: tuple[Path, ...] = (
    Path("app.py"),  # package root
    Path("cockpit") / "control_seat.py",
    Path("session") / "session.py",
    Path("menu") / "crawler.py",
    Path("loops") / "player.py",
)

_DOCSTRING_SCOPE_TYPES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _docstring_constant_ids(tree: ast.AST) -> set:
    """The ``id()`` of every ``ast.Constant`` node that is literally a
    module/class/function docstring -- the ``Constant`` inside the FIRST
    statement of a ``_DOCSTRING_SCOPE_TYPES`` scope's body, when that first
    statement is an ``Expr`` wrapping a string ``Constant``. Using node
    identity (rather than e.g. matching on line number or text) is the
    same technique ``test_spectate_no_send.py``'s
    ``_enclosing_function_scopes`` uses to key off of a specific AST node
    -- it's exact, with no risk of two different nodes on the same line
    colliding.

    A second (or later) bare string-literal statement in the same body is
    NOT a docstring by this rule, matching real Python semantics -- only
    the first statement of a scope is ever treated as its docstring."""
    ids = set()
    for scope in ast.walk(tree):
        if isinstance(scope, _DOCSTRING_SCOPE_TYPES) and scope.body:
            first = scope.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                ids.add(id(first.value))
    return ids


def _banned_vocab_hits(tree: ast.AST) -> list:
    """Every non-docstring string ``Constant`` under ``tree`` containing a
    banned term, as human-readable ``"line <n>: <term> in <repr>"``
    strings. Empty means clean. Deliberately walks the WHOLE tree (module
    level, every class, every function, every f-string fragment) rather
    than scoping to any particular construct -- a badge string could
    legitimately live in a module-level dict, a class attribute, or a
    function body, and this gate makes no assumption about which."""
    docstring_ids = _docstring_constant_ids(tree)
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docstring_ids:
            continue
        for term in _BANNED_TERMS:
            if term in node.value:
                hits.append(
                    f"line {getattr(node, 'lineno', '?')}: {term!r} in {node.value!r}"
                )
    return hits


def _scan_product_tree():
    """Returns ``(py_files, hits)`` -- ``py_files`` is every ``.py`` under
    ``tw2002_aiclient/`` (a non-empty list is itself a soundness check:
    an empty list means this test's own setup is broken, not that the
    product tree is clean); ``hits`` is every violation found, prefixed
    with its file path relative to the repo root so a failure message is
    immediately actionable."""
    py_files = sorted(_PRODUCT_ROOT.rglob("*.py"))
    hits = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(_PRODUCT_ROOT.parent)
        hits.extend(f"{rel}:{h}" for h in _banned_vocab_hits(tree))
    return py_files, hits


# ---------------------------------------------------------------------------
# The gate.
# ---------------------------------------------------------------------------


def test_product_tree_has_no_retired_mode_badge_vocabulary():
    py_files, hits = _scan_product_tree()
    assert py_files, (
        "expected .py files under tw2002_aiclient/ to scan -- this test's "
        "own setup is broken, not proof of anything"
    )
    assert not hits, (
        "retired AI-PILOT / ai_pilot / AUTO-LOOP vocabulary found in the "
        "product tree (docstrings citing the ban are exempt; these are "
        "not):\n" + "\n".join(hits)
    )


# ---------------------------------------------------------------------------
# Meta-tests -- prove the scanner itself is sound, independent of the real
# tree's current (clean) content. Mirrors test_spectate_no_send.py's own
# "prove the detector fires on a synthetic violation" discipline.
# ---------------------------------------------------------------------------


def test_scanner_detects_a_synthetic_ai_pilot_badge_string():
    src = 'BADGE = "AI-PILOT"\n'
    hits = _banned_vocab_hits(ast.parse(src))
    assert hits, "scanner failed to flag a literal 'AI-PILOT' string constant"
    assert "AI-PILOT" in hits[0]


def test_scanner_detects_a_synthetic_auto_loop_badge_string():
    src = 'BADGE = "AUTO-LOOP"\n'
    hits = _banned_vocab_hits(ast.parse(src))
    assert hits, "scanner failed to flag a literal 'AUTO-LOOP' string constant"
    assert "AUTO-LOOP" in hits[0]


def test_scanner_excludes_module_class_and_function_docstrings_citing_the_ban():
    """A docstring is exactly where this project's own ``D5: no
    ``ai_pilot``/imperative-mood text anywhere`` convention lives (see
    ``cockpit/hud.py``, ``fold.py``, ``tones.py``, ``liveness.py``,
    ``control_seat.py``, ``logsband.py`` today) -- citing the ban by name
    in a docstring must never itself trip the gate, at every scope the
    ban's own exclusion rule claims to cover."""
    module_src = '"""AI-PILOT is retired -- never render this badge again."""\n'
    assert _banned_vocab_hits(ast.parse(module_src)) == []

    class_src = (
        "class Cockpit:\n"
        '    """No AUTO-LOOP badge lives on this class."""\n'
        "    pass\n"
    )
    assert _banned_vocab_hits(ast.parse(class_src)) == []

    function_src = (
        "def compose_mode_badge(mode):\n"
        '    """D5: no ai_pilot/imperative-mood text anywhere."""\n'
        "    return mode.upper()\n"
    )
    assert _banned_vocab_hits(ast.parse(function_src)) == []


def test_scanner_still_fires_on_a_second_bare_string_statement_that_is_not_a_docstring():
    """Soundness edge case: only the FIRST statement of a scope's body is
    ever a syntactic docstring. A second bare string-literal statement
    that happens to look docstring-shaped (triple-quoted) is NOT one, and
    a banned term inside it must still fire -- otherwise a violation could
    hide immediately after a real docstring and evade the exclusion."""
    src = (
        "def f():\n"
        '    """A real docstring, unrelated."""\n'
        '    "AI-PILOT"\n'
    )
    hits = _banned_vocab_hits(ast.parse(src))
    assert hits, "a non-docstring bare string statement must still be scanned"


def test_scanner_detects_banned_fragment_inside_an_fstring():
    """f-string literal fragments surface as ordinary ``ast.Constant``
    nodes under the SAME ``JoinedStr`` (verified directly against this
    interpreter before relying on it here) -- ``ast.walk`` sees them with
    no special-casing required, so a banned term embedded in an f-string's
    static text must fire exactly like any other string constant."""
    src = 'label = f"mode={mode} AI-PILOT engaged"\n'
    hits = _banned_vocab_hits(ast.parse(src))
    assert hits, "scanner failed to flag a banned term inside an f-string fragment"
    assert "AI-PILOT" in hits[0]


def test_scanner_detects_lowercase_ai_pilot_as_a_dict_key_and_as_a_kwarg_value():
    dict_key_src = 'BADGES = {"ai_pilot": "App"}\n'
    hits_key = _banned_vocab_hits(ast.parse(dict_key_src))
    assert hits_key, "scanner failed to flag lowercase 'ai_pilot' used as a dict key"

    kwarg_value_src = 'render(mode="ai_pilot")\n'
    hits_kwarg = _banned_vocab_hits(ast.parse(kwarg_value_src))
    assert hits_kwarg, "scanner failed to flag lowercase 'ai_pilot' used as a kwarg value"


def test_scanner_is_case_sensitive_and_does_not_false_positive_on_unrelated_text():
    """The banned terms are matched by a plain, case-sensitive substring
    check -- a differently-cased rendering (e.g. lowercase ``"ai-pilot"``
    or the un-hyphenated ``"AI PILOT"``) is a DIFFERENT literal from the
    two real historical spellings this gate targets, and unrelated text
    containing neither spelling must stay clean. This is not a loophole:
    the two real spellings this project has ever used are ``AI-PILOT``
    (the badge label) and ``ai_pilot`` (the control-lock enum value) --
    both are exact-cased on purpose in ``_BANNED_TERMS``."""
    clean_src = (
        'BADGE = "App"\n'
        'MODE = "ai-pilot"\n'
        'LABEL = "AI PILOT MODE"\n'
    )
    assert _banned_vocab_hits(ast.parse(clean_src)) == []


def test_scan_product_tree_reaches_each_claimed_subpackage():
    """Identity floor, not cardinality (WO-BADGE-SCAN-IDENTITY-FLOOR).

    Dropping an entire subpackage still leaves dozens of `.py` files, so
    ``len(py_files) > 10`` never noticed a narrowed walk. Each package the
    gate claims to cover must contribute a named representative — mirror
    ``test_status_vocabulary_guard.test_the_scanner_reaches_the_files_it_
    claims_to_scan``.
    """
    py_files, _hits = _scan_product_tree()
    rel = {p.relative_to(_PRODUCT_ROOT) for p in py_files}
    missing = [str(p) for p in _SCAN_IDENTITY if p not in rel]
    assert not missing, (
        "product-tree discovery missed representative(s) — walk is incomplete "
        f"or a claimed package vanished: {missing}"
    )


def test_scan_identity_floor_goes_red_when_a_representative_is_dropped():
    """Falsify Accept: remove one representative from a real scan set →
    the identity check must notice. Restored set (the real walk) stays green
    via ``test_scan_product_tree_reaches_each_claimed_subpackage``."""
    py_files, _hits = _scan_product_tree()
    rel = {p.relative_to(_PRODUCT_ROOT) for p in py_files}
    victim = _SCAN_IDENTITY[1]  # cockpit/
    assert victim in rel, f"fixture assumed present: {victim}"
    forged = rel - {victim}
    missing = [p for p in _SCAN_IDENTITY if p not in forged]
    assert victim in missing, (
        "identity floor stayed silent after dropping a representative — "
        "the control is vacuous"
    )
