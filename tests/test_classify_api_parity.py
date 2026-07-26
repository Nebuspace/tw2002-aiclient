"""WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT -- structural enforcement, "enforce"
strategy (not "align").

`audit/session-classify-audit-coverage-20260726.md` C-01 found that bare
`classify()` never calls `_is_plain_timed_out_game_select` while
`classify_screen()` does. Reproducing the exact fixture the audit named
(a plain "Select a game :" prompt with a trailing "Timed out..." line)
shows parity ALREADY holds there -- `classify()`'s ordinary whole-text
`game_select` gate anchor matches "Select a game" directly, independent of
the missing pre-pass (see tests/test_classify.py's
`test_plain_game_select_with_timed_out_as_current_prompt_stays_game_select`).

The REAL, broader divergence -- not named by the audit's one-line finding,
confirmed while re-deriving it for this WO (and independently landed as the
2026-07-26T21:17Z Accept amendment) -- is structural, not shape-specific:
`classify()` has no notion of a "current prompt line" at all. Every
`_GATE_ANCHORS` matcher in its loop scans the WHOLE `rendered_text`
(classify.py's own `_ANCHORS` loop), so ANY gate anchor -- not just
`game_select` -- can fire on stale scrollback left over from an earlier
screen. `classify_screen()` scopes gate anchors to the live prompt line
specifically; `classify()` structurally cannot, no matter how many
pre-passes are bolted onto it. See
`test_stale_plain_game_select_bleeding_into_module_entry_menu_with_timed_out_is_not_game_select`
in tests/test_classify.py for the concrete fixture: `classify_screen()`
correctly reads a stale "Select a game :" line as the current `menu`
prompt's `menu`; `classify()` still misreads it as `game_select`.

Given that -- and that grepping the product tree turns up ZERO live
consumers of the bare `classify` name (every real call site imports
`classify_screen` instead: `Session.classify()` in session/session.py,
menu/crawler.py, loops/player.py, loops/recorder.py, session/guardian.py,
session/protocol.py, session/login.py) -- "align" (bolting the missing
pre-pass onto `classify()`) was rejected: it would satisfy only the one
shape the audit happened to name while leaving the function stale-blind on
every OTHER gate anchor, and would read as "parity is now enforced" to a
future reader when the structural hole is still wide open. "Enforce" is
the chosen strategy: `classify()` stays exactly what its own docstring
already said -- for a single isolated string (tests, one-off checks) only
-- and this file is the failing pin that fires if a PRODUCT-TREE caller
ever reaches for it instead of `classify_screen()`.

Two independent kinds of evidence, mirroring
tests/test_menu_crawl_chokepoint.py's own discipline:

  * a **structural sweep** -- an AST scan of every module under
    `tw2002_aiclient/` (excluding `session/classify.py`, the definition
    site, and `tests/`, which legitimately uses the bare function for
    isolated-string checks per its own docstring) proving no product-tree
    caller imports the bare `classify` name, directly or via a submodule
    alias, and none reaches it reflectively via `getattr`;
  * **bypass meta-tests** -- proving the scanner itself would catch a
    reintroduced violation, in four shapes: a direct import, an ALIASED
    direct import, a submodule-alias import later called as
    `<alias>.classify(...)` (the same aliasing evasion
    tests/test_menu_crawl_chokepoint.py's own scanner resolves for its
    send primitive -- a name-only scan would miss
    `from ..session import classify as csf; csf.classify(text)`, since no
    node anywhere reads the literal name `classify` as an import target),
    and a reflective `getattr(module, "classify")` call (no import
    statement at all -- caught by name, not by import shape).

**Disclosed residual**, same posture as
tests/test_mode_badge_vocabulary.py's own disclosed gap: a dynamically
ASSEMBLED attribute name (`getattr(module, "class" + "ify")`) or a
keyword-argument `getattr(module, name="classify")` produces no single AST
node this static scan can key on, and is outside its reach. Reflection is
checked by the literal string `"classify"` rather than banned outright
(unlike the money-safety chokepoint in test_menu_crawl_chokepoint.py) --
this is a correctness contract, not a security boundary, so banning every
`getattr` call in the product tree would be disproportionate to the risk.
"""

import ast
from pathlib import Path

_PRODUCT_ROOT = Path(__file__).resolve().parent.parent / "tw2002_aiclient"
_CLASSIFY_MODULE_FILE = _PRODUCT_ROOT / "session" / "classify.py"


def _classify_import_findings(tree):
    """Every way `tree` could reach the bare `classify` function:

    - a DIRECT import, `from <...>.classify import classify [as y]` --
      the module path's last component IS `classify`, so the name being
      imported is the FUNCTION;
    - a SUBMODULE alias, `from <...> import classify [as y]` -- the
      module path's last component is NOT `classify`, so the name being
      imported is the classify.py MODULE ITSELF (mirrors
      tests/test_classify.py's own
      `from tw2002_aiclient.session import classify as classify_module`),
      tracked so a later `<alias>.classify(...)` call through it is also
      caught.

    Returns `(direct_hits, module_aliases)` where `direct_hits` is a list
    of `(lineno, bound_as)` and `module_aliases` is the set of local names
    bound to the classify SUBMODULE (not yet known to be misused -- the
    caller resolves those against actual `.classify(...)` call sites)."""
    direct_hits = []
    module_aliases = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        last_component = module.split(".")[-1]
        for alias in node.names:
            if alias.name != "classify":
                continue
            bound_as = alias.asname or alias.name
            if last_component == "classify":
                direct_hits.append((node.lineno, bound_as))
            else:
                module_aliases.add(bound_as)
    return direct_hits, module_aliases


def _classify_call_findings(tree, module_aliases):
    """Every `<alias>.classify(...)` call where `alias` is one of the
    submodule aliases `_classify_import_findings` found -- the aliasing
    evasion a name-only import scan can't see on its own."""
    hits = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "classify"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_aliases
        ):
            hits.append(node.lineno)
    return hits


def _reflection_findings(tree):
    """Every `getattr(<anything>, "classify", ...)` call -- a reflective
    reach for the bare function that no import-based check can see at
    all: no `from X import classify` statement ever appears, so
    `_classify_import_findings` has nothing to key on. Scoped to the
    literal attribute-name string `"classify"`, not a ban on `getattr`
    itself (see module docstring for why an outright ban would be
    disproportionate here)."""
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"):
            continue
        if len(node.args) < 2:
            continue
        attr_arg = node.args[1]
        if isinstance(attr_arg, ast.Constant) and attr_arg.value == "classify":
            hits.append(node.lineno)
    return hits


def _scan_file(path):
    """Human-readable violation strings for one file, or `[]` if clean."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    direct_hits, module_aliases = _classify_import_findings(tree)
    call_hits = _classify_call_findings(tree, module_aliases) if module_aliases else []
    reflection_hits = _reflection_findings(tree)
    hits = [f"line {lineno}: imports bare classify() as {bound_as!r}" for lineno, bound_as in direct_hits]
    hits += [f"line {lineno}: calls classify() via a submodule alias" for lineno in call_hits]
    hits += [f"line {lineno}: reaches classify() via getattr(..., 'classify')" for lineno in reflection_hits]
    return hits


def _scan_product_tree():
    """`(py_files, hits)` over every `.py` under `tw2002_aiclient/` except
    `session/classify.py` itself (the definition site -- it doesn't
    "import" its own function, so it would never trip these checks
    anyway, but excluding it keeps the scan's intent explicit)."""
    py_files = sorted(p for p in _PRODUCT_ROOT.rglob("*.py") if p != _CLASSIFY_MODULE_FILE)
    hits = []
    for path in py_files:
        rel = path.relative_to(_PRODUCT_ROOT.parent)
        hits.extend(f"{rel}:{h}" for h in _scan_file(path))
    return py_files, hits


# ---------------------------------------------------------------------------
# The gate.
# ---------------------------------------------------------------------------


def test_product_tree_never_reaches_bare_classify():
    py_files, hits = _scan_product_tree()
    assert py_files, (
        "expected .py files under tw2002_aiclient/ to scan -- this test's "
        "own setup is broken, not proof of anything"
    )
    assert not hits, (
        "a product-tree module reaches the stale-scrollback-unsafe bare "
        "classify() function instead of classify_screen() -- see "
        "classify.py's classify() docstring (WO-CLASSIFY-API-PARITY-"
        "PLAIN-TIMEOUT, 'enforce' strategy) for why this is refused rather "
        "than patched:\n" + "\n".join(hits)
    )


# ---------------------------------------------------------------------------
# Non-vacuity: the sweep is exercising real, known consumers, not an empty
# or accidentally-narrowed tree.
# ---------------------------------------------------------------------------


def test_scan_includes_the_known_classify_screen_consumers():
    """If these file paths ever stopped resolving (a rename, a package
    reshuffle) the sweep above would keep passing for the wrong reason --
    silently scanning nothing meaningful. Pin that the known consumers are
    still part of what gets scanned."""
    py_files, _hits = _scan_product_tree()
    rel_paths = {p.relative_to(_PRODUCT_ROOT.parent).as_posix() for p in py_files}
    for expected in (
        "tw2002_aiclient/session/session.py",
        "tw2002_aiclient/menu/crawler.py",
        "tw2002_aiclient/loops/player.py",
        "tw2002_aiclient/loops/recorder.py",
        "tw2002_aiclient/session/guardian.py",
        "tw2002_aiclient/session/protocol.py",
        "tw2002_aiclient/session/login.py",
    ):
        assert expected in rel_paths, f"expected consumer {expected!r} missing from the scan"


# ---------------------------------------------------------------------------
# Bypass meta-tests -- prove the scanner is not fooled, independent of the
# real tree's current (clean) content. Mirrors
# tests/test_menu_crawl_chokepoint.py's and
# tests/test_mode_badge_vocabulary.py's own "prove the detector fires on a
# synthetic violation" discipline.
# ---------------------------------------------------------------------------


def _hits_for_source(src):
    tree = ast.parse(src)
    direct_hits, module_aliases = _classify_import_findings(tree)
    call_hits = _classify_call_findings(tree, module_aliases) if module_aliases else []
    reflection_hits = _reflection_findings(tree)
    return direct_hits, call_hits, reflection_hits


def test_scanner_catches_a_direct_bare_classify_import():
    direct_hits, _call_hits, _reflection_hits = _hits_for_source("from ..session.classify import classify\n")
    assert direct_hits


def test_scanner_catches_an_aliased_direct_classify_import():
    direct_hits, _call_hits, _reflection_hits = _hits_for_source(
        "from tw2002_aiclient.session.classify import classify as _c\n"
    )
    assert direct_hits and direct_hits[0][1] == "_c"


def test_scanner_catches_a_submodule_aliased_classify_call():
    """The aliasing evasion a name-only import scan misses: no AST node
    anywhere reads the literal string 'classify' as an import of the
    function -- `from ..session import classify as csf` imports the
    MODULE. The violation only exists at the CALL site, `csf.classify(...)`."""
    direct_hits, call_hits, _reflection_hits = _hits_for_source(
        "from ..session import classify as csf\n"
        "def sneaky(text):\n"
        "    return csf.classify(text)\n"
    )
    assert not direct_hits
    assert call_hits


def test_scanner_catches_a_reflective_getattr_classify_call():
    """No `from X import classify` statement appears at all here -- the
    import-based checks above have nothing to key on. Only the reflection
    check (`_reflection_findings`) can see this."""
    direct_hits, call_hits, reflection_hits = _hits_for_source(
        "def sneaky(module, text):\n"
        "    fn = getattr(module, 'classify')\n"
        "    return fn(text)\n"
    )
    assert not direct_hits
    assert not call_hits
    assert reflection_hits


def test_scanner_does_not_flag_classify_screen_imports():
    direct_hits, call_hits, reflection_hits = _hits_for_source(
        "from ..session.classify import classify_screen\n"
    )
    assert not direct_hits
    assert not call_hits
    assert not reflection_hits


def test_scanner_does_not_flag_a_submodule_alias_used_only_for_other_names():
    """A module alias bound the same way tests/test_classify.py's own
    `classify_module` is (`from tw2002_aiclient.session import classify as
    classify_module`) is not itself a violation -- only a subsequent
    `<alias>.classify(...)` call is. Using the alias for anything else
    (e.g. reading a frozenset off it, as real code does) must not
    false-positive."""
    direct_hits, call_hits, reflection_hits = _hits_for_source(
        "from tw2002_aiclient.session import classify as classify_module\n"
        "def reads_a_constant():\n"
        "    return classify_module.NEVER_AUTO_ACTION_CLASSES\n"
    )
    assert not direct_hits
    assert not call_hits
    assert not reflection_hits


def test_scanner_does_not_flag_a_getattr_call_for_a_different_attribute():
    """`getattr(x, "classify_screen")` -- or any attribute name other than
    the exact literal `"classify"` -- must not false-positive; the
    reflection check is scoped to the one banned name, not to `getattr`
    itself."""
    _direct_hits, _call_hits, reflection_hits = _hits_for_source(
        "def reads_something_else(module):\n"
        "    return getattr(module, 'classify_screen')\n"
    )
    assert not reflection_hits
