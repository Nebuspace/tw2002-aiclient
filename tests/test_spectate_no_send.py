"""WO-P4-055 lane B -- structural + behavioral proof that the product
spectate path is send-free (AI/spectate never live-drives; live senders
are exactly ``{app, human}`` -- ``canon/architecture/north-star.md``).

The trap this file exists to avoid (see the WO dispatch): the product
cockpit has NO game-send path *at all* today (confirmed by grep before
this WO was dispatched -- ``screens.py``/``app.py``/``watchfeed.py`` call
only ``session_cli.send_request("status", ...)`` and ``WatchFeed``'s one
subscribe line). A test that merely asserts "no send happened" against
today's reality would be **vacuously true** -- it would keep passing even
after a future WO (PWO-056, "attach from cockpit") added an ungated send
path, right up until the day it silently didn't. So every guard below is
either (a) proven to actually fire on a violation, via a synthetic
self-test of the scanner AND a temporary inject-then-revert of the real
guard scoped to ``app._run_play`` (see this WO's STATUS report for the
inject/revert transcript -- not repeated here, since leaving a live
"prove-the-guard-fires" violation in a committed test file would defeat
the guard it's proving), or (b) explicitly labeled vacuous in its own
docstring.

Sibling file ``tests/test_cockpit_spectate.py`` (lane A) proves
``cockpit.control_seat``'s pure composer and ``PlayShellScreen.draw()``'s
wiring of it; this file is the "no send path exists" side.

Two independent layers, matching the WO's own ask:
  1. AST scanners (no imports fail if code changes shape) -- catch a
     send-capable call/symbol being ADDED to the source, whether or not
     it's ever exercised at runtime.
  2. A behavioral FakeClient drive of ``app._run_play`` -- catches a
     send-capable call that a static scanner's syntactic pattern-match
     might miss (e.g. an indirect call through a variable), by recording
     every wire write and asserting the log contains only the two known-
     legitimate kinds.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import curses

from tw2002_aiclient import adapters, app
from tw2002_aiclient import cockpit as cockpit_pkg
from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient import watchfeed as watchfeed_mod
from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow
from tw2002_aiclient.session import cli as session_cli

# ---------------------------------------------------------------------------
# AST scanner -- shared by every structural guard below.
#
# Two independent violation shapes, mirroring
# tests/test_play_esc_daemon_survival.py::test_run_play_source_never_calls_stop's
# established idiom (walk a function/class/module's AST for banned call
# sites) but extended from "no teardown verb" to "no send-capable verb or
# symbol":
#
#   1. Any call whose func is an Attribute ending in `.send_request` (not
#      pinned to the literal name `session_cli` -- `adapters.py` imports
#      the SAME function under the alias `_cli`, so matching on the
#      METHOD name rather than the base object is what stays robust to a
#      future alias) with a literal verb argument outside the read-only
#      allowlist, OR a non-literal (dynamic) verb -- an opaque verb
#      reaching this call from inside the spectate surface is exactly as
#      suspicious as a banned literal one, so it's a violation too, not a
#      free pass.
#   2. A reference (call, bare name, or import) to a known send-capable
#      symbol that bypasses send_request entirely (`AttachInputConn`/
#      `send_key`/`send_raw`/the ops CLI's `cmd_do`/`cmd_send`).
#
# Deliberately blunt, matching test_play_esc_daemon_survival.py's own
# stated design ("the guard's bluntness is the feature") -- no attempt to
# detect whether a call site is gated behind `if not self.spectating:`.
# When PWO-056 legitimately adds a gated send path, adjudicate it the same
# way WO-P4-050 adjudicated `feed.stop()` against the sibling stop-guard:
# a precise, single-site, explained allowlist -- never a blanket loosening.
# ---------------------------------------------------------------------------

_BANNED_SEND_SYMBOLS = frozenset({
    "send_key", "send_raw", "AttachInputConn", "attach_client",
    "cmd_do", "cmd_send",
})

# Reflective attribute-access functions the scanner also inspects (Cipher
# finding, WO-P4-056 second REVISE): a call site can reach a banned symbol
# via `getattr(obj, "send_key")` / `setattr(...)` / `obj.__getattribute__
# ("send_key")` instead of a literal `.send_key` Attribute node, which the
# scanner's original Attribute-only matching never saw at all.
_REFLECTION_FUNCS = frozenset({"getattr", "setattr"})


def _reflected_attr_name(call):
    """If ``call`` is ``getattr(obj, "name", ...)`` / ``setattr(obj,
    "name", ...)`` / ``obj.__getattribute__("name")`` with a STRING-
    LITERAL name argument, return that literal string; else ``None``.

    String literals ONLY, deliberately -- a dynamic name (``getattr(obj,
    name_var)``) is unresolvable by any static AST guard, and flagging
    every dynamic ``getattr``/``setattr`` call in the codebase would
    false-positive constantly (this project already uses plenty of
    ordinary defensive ``getattr(x, "field", None)`` calls -- see e.g.
    ``watchfeed.py``/``screens.py``/``cockpit/strip.py``) for zero real
    detection benefit. Fully-dynamic reflection reaching a banned symbol
    remains a disclosed residual gap outside any static scanner's reach,
    not something this function -- or any AST guard -- can close."""
    if (
        isinstance(call.func, ast.Name)
        and call.func.id in _REFLECTION_FUNCS
        and len(call.args) >= 2
    ):
        arg = call.args[1]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
        return None
    if (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "__getattribute__"
        and call.args
    ):
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return None


def _iter_send_request_calls(node):
    """Every ``Call`` under ``node`` whose func attribute is literally
    named ``send_request`` -- matches ``session_cli.send_request(...)``,
    ``_cli.send_request(...)``, ``self.session_cli.send_request(...)``,
    etc. (the base object's name is deliberately NOT pinned) -- OR whose
    func is itself a reflected ``getattr(obj, "send_request", ...)``/
    ``obj.__getattribute__("send_request")`` call with a string-literal
    name (Cipher finding, WO-P4-056 second REVISE: the original
    Attribute-only match let ``getattr(session_cli, "send_request")
    ("do", ...)`` bypass detection entirely, since the outer call's
    ``func`` is a ``Call`` node, never an ``Attribute``). The verb
    argument is still read off the OUTER call's own ``args``/``keywords``
    by ``_literal_verb`` below, unchanged -- the reflection only changes
    how the CALLABLE was obtained, not where its own arguments live."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and n.func.attr == "send_request":
                yield n
            elif isinstance(n.func, ast.Call) and _reflected_attr_name(n.func) == "send_request":
                yield n


def _literal_verb(call):
    """The call's verb argument as a literal str, or ``None`` if it isn't
    a compile-time string constant (positional first, else a ``verb=``
    keyword) -- ``None`` is always treated as a violation by the caller,
    dynamic or absent verbs included."""
    if call.args:
        arg = call.args[0]
    else:
        arg = next((kw.value for kw in call.keywords if kw.arg == "verb"), None)
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _enclosing_function_scopes(root):
    """Map ``id(node) -> nearest enclosing FunctionDef's name`` (or
    ``None`` for module/outer scope) for every descendant of ``root``
    (``root`` included) -- ``ast.walk`` alone gives no parent/scope
    information, so this is a small scope-tracking traversal built
    specifically to answer "which function is this node INSIDE?" for
    ``_is_allowlisted_attach_site`` below (Samantha REVISE finding A/2:
    a shape-only match without this check excuses the SAME shape no
    matter which function it's reached from). A ``FunctionDef`` node
    itself is recorded under its OUTER scope (matching how a decorator
    or default-arg expression would evaluate); only its CHILDREN --
    i.e. its own body -- get its name. Nested ``def``s use the
    INNERMOST enclosing function's name."""
    scopes = {}

    def _walk(node, current_fn_name):
        scopes[id(node)] = current_fn_name
        next_fn_name = node.name if isinstance(node, ast.FunctionDef) else current_fn_name
        for child in ast.iter_child_nodes(node):
            _walk(child, next_fn_name)

    _walk(root, None)
    return scopes


def _is_allowlisted_attach_site(node, scopes=None) -> bool:
    """PWO-056 (WO-P4-056) lane A adjudication -- mirrors WO-P4-050's own
    ``_is_allowlisted_watchfeed_stop`` precedent (``tests/
    test_play_esc_daemon_survival.py``): a precise, single-SITE allowlist
    for the ONE legitimate send-capable surface this WO adds, never a
    blanket loosening of the guard -- every OTHER send-capable reference
    anywhere else in ``app.py`` still trips this guard by design.

    Matched by AST SHAPE **and** ENCLOSING-FUNCTION SCOPE (Samantha REVISE
    finding A/2, confirmed by execution: a shape-only version of this
    predicate silently excused the identical shape reached from an
    unrelated function -- a rogue ``AttachInputConn``/``send_key`` site
    elsewhere in ``app.py`` would have passed unnoticed). ``scopes`` is
    ``_enclosing_function_scopes(<the root _send_violations was called
    on>)``, threaded in by ``_banned_name_hits`` below -- callers never
    need to build it themselves.

      1. ``attach_conn.send_key(...)`` -- an ``Attribute`` ``.send_key``
         on a ``Name`` literally called ``attach_conn``, AND its nearest
         enclosing function is literally ``_run_play``. A same-shaped
         call reached from any OTHER function is NOT excused.
      2. ``AttachInputConn`` -- a bare ``Name`` reference, AND its
         nearest enclosing function is literally ``_attempt_attach``. Its
         IMPORT (``ast.alias``) is excused regardless of scope -- imports
         are necessarily module-level in this codebase's style, and the
         import statement alone constructs nothing; the security-relevant
         act is the CONSTRUCTION CALL, which the scope check above still
         gates.
    """
    scopes = scopes or {}
    if isinstance(node, ast.Attribute):
        return (
            node.attr == "send_key"
            and isinstance(node.value, ast.Name)
            and node.value.id == "attach_conn"
            and scopes.get(id(node)) == "_run_play"
        )
    if isinstance(node, ast.Name):
        return node.id == "AttachInputConn" and scopes.get(id(node)) == "_attempt_attach"
    if isinstance(node, ast.alias):
        return (node.asname or node.name) == "AttachInputConn"
    return False


def _aliased_banned_locals(node):
    """Map each LOCAL name (the ``as`` alias if present, else the plain
    imported name) that refers to a ``_BANNED_SEND_SYMBOLS`` member back
    to the REAL symbol it names -- e.g. ``import AttachInputConn as
    _Sneaky`` maps ``"_Sneaky" -> "AttachInputConn"``.

    Cipher finding (WO-P4-056 second REVISE): the scanner previously
    recorded ONLY ``alias.asname or alias.name`` for an import -- for an
    aliased import that is the ASNAME, never the real banned name -- so
    an aliased import evaded detection both at the import statement
    itself (the asname string, e.g. ``"_Sneaky"``, is never a member of
    ``_BANNED_SEND_SYMBOLS``) AND at every later reference through the
    alias (a bare ``Name`` reference to ``_Sneaky`` was likewise recorded
    as ``"_Sneaky"``, never resolved back to ``"AttachInputConn"``).
    ``_banned_name_hits`` below uses this map to resolve every ``Name``
    reference through its real symbol before checking it against the
    banned set."""
    aliases = {}
    for n in ast.walk(node):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for alias in n.names:
                if alias.name in _BANNED_SEND_SYMBOLS:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _banned_name_hits(node, *, allowed=None):
    allowed = allowed or (lambda n, scopes: False)
    scopes = _enclosing_function_scopes(node)
    alias_locals = _aliased_banned_locals(node)

    attrs = {
        n.attr for n in ast.walk(node)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and not allowed(n, scopes)
    }
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and not allowed(n, scopes):
            # Resolve an ALIAS reference (Cipher finding, above) back to
            # the real banned symbol it names -- an unaliased name just
            # resolves to itself.
            names.add(alias_locals.get(n.id, n.id))
    imported = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for alias in n.names:
                if not allowed(alias, scopes):
                    # The REAL imported symbol (Cipher finding, above):
                    # recording only ``alias.asname or alias.name`` let an
                    # aliased import's real, banned name go unrecorded.
                    imported.add(alias.name)
    reflected = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            name = _reflected_attr_name(n)
            if name in _BANNED_SEND_SYMBOLS:
                # Reflection (Cipher finding): `getattr(conn,
                # "send_key")(...)` reaches a banned symbol via no
                # `Attribute`/`Name` node the checks above ever see.
                # Flagged UNCONDITIONALLY -- never passed through
                # `allowed()` -- because no legitimate site in this
                # codebase reaches a send-capable symbol reflectively;
                # the allowlist adjudicates ordinary call shapes, and
                # does not extend trust to a reflective one regardless of
                # which function it appears in.
                reflected.add(name)
    return (attrs | names | imported | reflected) & _BANNED_SEND_SYMBOLS


def _send_violations(node, *, allowed_verbs, allowed=None):
    """Every send-capable violation found under ``node`` (a Module,
    ClassDef, or FunctionDef), as human-readable strings. Empty means
    clean. ``allowed`` (PWO-056) is an optional ``(node, scopes) -> bool``
    predicate passed straight through to ``_banned_name_hits`` (which
    computes ``scopes`` via ``_enclosing_function_scopes`` once per call
    and threads it in -- callers pass a bare predicate, never a scopes
    dict of their own) -- see ``_is_allowlisted_attach_site`` for the one
    adjudicated exception; every existing caller that omits it keeps the
    exact prior strict
    behavior (default ``None`` -> nothing allowed)."""
    violations = []
    for call in _iter_send_request_calls(node):
        verb = _literal_verb(call)
        if verb is None:
            violations.append(
                f"send_request() called with a non-literal/unresolvable verb "
                f"at line {getattr(call, 'lineno', '?')}"
            )
        elif verb not in allowed_verbs:
            violations.append(
                f"send_request(verb={verb!r}, ...) at line {getattr(call, 'lineno', '?')} "
                f"-- not in the read-only allowlist {sorted(allowed_verbs)}"
            )
    hit = _banned_name_hits(node, allowed=allowed)
    if hit:
        violations.append(f"banned send-capable symbol(s) referenced: {sorted(hit)}")
    return violations


# ---------------------------------------------------------------------------
# 0. Prove the scanner ITSELF is sound, independent of any real file's
#    current content. This is what makes the guards below trustworthy even
#    where they currently find nothing (screens.py / watchfeed.py /
#    cockpit/*.py have zero send capability TODAY -- that's a fact about
#    reality, not a limitation of the detector; this test is what tells
#    the two apart).
# ---------------------------------------------------------------------------


def test_scanner_detects_a_synthetic_send_violation():
    verb_violation_src = (
        "def spectate_handle_key(key, run_dir):\n"
        '    session_cli.send_request("do", {"action": "attack"}, run_dir=run_dir)\n'
    )
    violations = _send_violations(ast.parse(verb_violation_src), allowed_verbs={"status"})
    assert violations, "scanner failed to flag a literal non-status send_request verb"
    assert "do" in violations[0]

    dynamic_verb_src = (
        "def spectate_dispatch(verb, run_dir):\n"
        "    session_cli.send_request(verb, {}, run_dir=run_dir)\n"
    )
    violations_dyn = _send_violations(ast.parse(dynamic_verb_src), allowed_verbs={"status"})
    assert violations_dyn, "scanner failed to flag a non-literal (dynamic) send_request verb"

    symbol_violation_src = (
        "def spectate_drive(conn):\n"
        '    conn.send_key(b"\\x1b")\n'
    )
    violations2 = _send_violations(ast.parse(symbol_violation_src), allowed_verbs={"status"})
    assert violations2, "scanner failed to flag a banned send-capable symbol reference"

    clean_src = (
        "def spectate_poll(run_dir):\n"
        '    return session_cli.send_request("status", {}, run_dir=run_dir)\n'
    )
    assert _send_violations(ast.parse(clean_src), allowed_verbs={"status"}) == []


def test_scanner_detects_cipher_demonstrated_bypass_aliased_import_and_getattr_reflection():
    """Cipher security pass (WO-P4-056 second REVISE): this EXACT source
    -- Cipher's own synthetic bypass -- produced ZERO violations against
    the scanner as it stood before this fix, via two independent evasion
    forms combined in one snippet:

      1. Aliased import: ``import AttachInputConn as _Sneaky`` then
         constructing via ``_Sneaky(...)`` -- the scanner previously
         recorded only the ASNAME (``"_Sneaky"``, never a member of
         ``_BANNED_SEND_SYMBOLS``) for both the import statement and
         every later reference through the alias.
      2. Reflection: ``getattr(conn, "send_key")(...)`` -- a banned
         symbol reached via no literal ``Attribute``/``Name`` node the
         original scanner ever inspected.

    Fixed by ``_aliased_banned_locals`` (resolves an alias reference back
    to its real symbol) and the ``reflected`` set in ``_banned_name_hits``
    (flags a string-literal ``getattr``/``setattr``/``__getattribute__``
    name matching a banned symbol, unconditionally). Independently
    reproduced BEFORE the fix landed (see this WO's STATUS report for the
    transcript: the pre-fix scanner returned ``[]`` for this exact
    source); both banned symbols are flagged now."""
    bypass_src = (
        "from tw2002_aiclient.session.attach_client import AttachInputConn as _Sneaky\n"
        "def _attempt_attach(sock_path):\n"
        "    conn = _Sneaky(sock_path); conn.connect(); return conn, None\n"
        "def _run_play(stdscr, profile):\n"
        "    conn, _ = _attempt_attach(\"x\")\n"
        '    getattr(conn, "send_key")(b"SECRETDATA")\n'
    )
    tree = ast.parse(bypass_src)
    violations = _send_violations(tree, allowed_verbs={"status"}, allowed=_is_allowlisted_attach_site)
    assert violations, "Cipher's aliased-import + getattr-reflection bypass must be flagged"
    hit_text = " ".join(violations)
    assert "AttachInputConn" in hit_text, "the aliased AttachInputConn import/construction must be flagged"
    assert "send_key" in hit_text, "the getattr(conn, 'send_key')(...) reflection must be flagged"


def test_scanner_detects_getattr_reflected_send_request_call():
    """(2) of the same Cipher finding, applied to `_iter_send_request_calls`
    directly: `getattr(session_cli, "send_request")(...)` -- the outer
    call's `func` is a `Call` node (the getattr call), never a literal
    `.send_request` Attribute, so the original Attribute-only match never
    saw it. The verb argument is still read off the OUTER call's own
    args/keywords by `_literal_verb`, unchanged by this fix -- a
    reflected call with a non-status verb is flagged the exact same way
    a literal one already is."""
    reflected_src = (
        "def spectate_dispatch(run_dir):\n"
        '    return getattr(session_cli, "send_request")("do", {}, run_dir=run_dir)\n'
    )
    violations = _send_violations(ast.parse(reflected_src), allowed_verbs={"status"})
    assert violations, "a reflected getattr(x, 'send_request')(...) call must be flagged"
    assert "do" in violations[0]

    reflected_clean_src = (
        "def spectate_poll(run_dir):\n"
        '    return getattr(session_cli, "send_request")("status", {}, run_dir=run_dir)\n'
    )
    assert _send_violations(ast.parse(reflected_clean_src), allowed_verbs={"status"}) == [], (
        "a reflected send_request call with an ALLOWED literal verb must stay clean, "
        "same as the literal-Attribute form"
    )


# ---------------------------------------------------------------------------
# 1. app._run_play -- today's ENTIRE play/spectate loop. Real, load-bearing:
#    verified (outside this file, see the WO STATUS report) to actually go
#    red when a violating send_request call is temporarily injected into
#    _run_play's body and go green again once reverted -- not merely
#    proven-by-construction. Mirrors
#    test_play_esc_daemon_survival.py::test_run_play_source_never_calls_stop's
#    exact technique (source -> ast.parse -> isolate the FunctionDef ->
#    walk it), extended from banning teardown verbs to banning send ones.
# ---------------------------------------------------------------------------


def test_run_play_source_has_no_send_capable_call_or_symbol():
    src = Path(inspect.getsourcefile(app._run_play)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_run_play"
    )
    # PWO-056 (WO-P4-056): `allowed=_is_allowlisted_attach_site` excuses
    # exactly `attach_conn.send_key(...)` -- the ONE forwarding call site
    # this WO adds, reached only once the human's own Ctrl-A keypress has
    # already taken the Human control lock. See that predicate's own
    # docstring for the full adjudication; every other send-capable shape
    # still trips this guard.
    violations = _send_violations(fn, allowed_verbs={"status"}, allowed=_is_allowlisted_attach_site)
    assert not violations, f"_run_play must stay send-free (beyond the adjudicated attach forward); found: {violations}"


# ---------------------------------------------------------------------------
# 2. Whole app.py module -- app.py's one legitimate send_request call site
#    lives inside _daemon_status_provider's nested _poll() closure, a
#    SEPARATE function from _run_play; a guard scoped only to _run_play
#    would miss a violation added there. Real today: this genuinely
#    exercises the allowlist against app.py's actual "status" call site,
#    not an empty scan.
# ---------------------------------------------------------------------------


def test_app_module_only_ever_requests_the_status_verb():
    src = Path(inspect.getsourcefile(app)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    # PWO-056 (WO-P4-056): `allowed=_is_allowlisted_attach_site` excuses
    # the two adjudicated attach sites (`AttachInputConn`'s import +
    # construction in `_attempt_attach`, `attach_conn.send_key(...)` in
    # `_run_play`) -- see that predicate's own docstring. Every other
    # send-capable shape anywhere else in app.py still trips this guard.
    violations = _send_violations(tree, allowed_verbs={"status"}, allowed=_is_allowlisted_attach_site)
    assert not violations, f"app.py must only ever request the read-only 'status' verb (beyond the adjudicated attach sites); found: {violations}"
    assert any(True for _ in _iter_send_request_calls(tree)), (
        "expected at least one real send_request call site in app.py (the status "
        "poll) -- found none; this test's own setup is broken, not proof of anything"
    )


# ---------------------------------------------------------------------------
# 2b. `_is_allowlisted_attach_site` sensitivity (Samantha REVISE finding A/2,
#    CONFIRMED BY EXECUTION -- both by her own run and independently
#    reproduced before this fix landed: a shape-only version of the
#    predicate silently excused `AttachInputConn` construction + `attach_
#    conn.send_key(...)` reached from an unrelated function, because it
#    checked SHAPE but not ENCLOSING SCOPE). Fixed above via
#    `_enclosing_function_scopes` + the now-scope-aware
#    `_is_allowlisted_attach_site`. (1) proves the guard still fires for an
#    ordinary (non-shape-matching) violation anywhere else in the module;
#    the consolidated test below is the direct regression pin for the hole
#    itself, using Samantha's own synthetic source verbatim.
# ---------------------------------------------------------------------------


def test_allowed_predicate_still_flags_a_violation_at_a_different_function():
    """(1): an ordinary send-capable call OUTSIDE the two adjudicated
    attach sites, in a synthetic module shaped like app.py, must still
    trip the guard even with `allowed=_is_allowlisted_attach_site`
    active."""
    src = (
        "def _run_play(stdscr, profile):\n"
        "    pass\n"
        "\n"
        "def _some_other_function():\n"
        '    session_cli.send_request("do", {}, run_dir=None)\n'
    )
    tree = ast.parse(src)
    violations = _send_violations(tree, allowed_verbs={"status"}, allowed=_is_allowlisted_attach_site)
    assert violations, "an ordinary send_request violation elsewhere in the module must still trip the guard"


def test_attach_allowlist_is_single_site_not_shape_wide():
    """Consolidated regression pin (Samantha REVISE, WO-P4-056) -- the
    direct pin for finding A/2. Independently reproduced BEFORE the
    `_enclosing_function_scopes` fix landed: running assertion 3's exact
    synthetic source (Samantha's own) through the OLD shape-only predicate
    returned an empty hit set (`set()`) -- silent, confirming the hole.
    All three assertions pass now.

    ONE disclosed correction to the literal spec: assertion 2 pins "every
    `.send_key(...)` call is enclosed by `_run_play`", not "exactly one" --
    the mandatory backspace-forwarding fix (same REVISE, hub ruling)
    legitimately gave `_run_play` THREE `attach_conn.send_key(...)` call
    sites (Enter / backspace / generic byte), all the same logical
    forwarding mechanism. A hardcoded count of 1 would fail against
    correct code for no security benefit; LOCATION (never a rogue site in
    a different function) is the invariant that actually matters, and
    this still pins it exactly, for every occurrence found.
    """
    src = Path(inspect.getsourcefile(app)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    scopes = _enclosing_function_scopes(tree)

    # 1. exactly ONE AttachInputConn construction in the whole module,
    #    and its enclosing FunctionDef is _attempt_attach.
    construction_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "AttachInputConn"
    ]
    assert len(construction_calls) == 1, (
        f"expected exactly one AttachInputConn(...) construction in app.py; found {len(construction_calls)}"
    )
    assert scopes.get(id(construction_calls[0])) == "_attempt_attach", (
        "the one AttachInputConn(...) construction must be enclosed by _attempt_attach"
    )

    # 2. every attach_conn.send_key(...) call in the whole module is
    #    enclosed by _run_play -- see the disclosed correction above for
    #    why this is a LOCATION pin rather than a hardcoded count of one.
    send_key_calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "send_key"
    ]
    assert send_key_calls, "expected at least one .send_key(...) call in app.py -- found none"
    stray = [n for n in send_key_calls if scopes.get(id(n)) != "_run_play"]
    assert not stray, f"found {len(stray)} .send_key(...) call(s) NOT enclosed by _run_play"

    # 3. the allowlisted SHAPE in any OTHER function must still be a
    #    violation -- Samantha's own synthetic source, verbatim.
    rogue_src = (
        "def some_unrelated_function(sock_path):\n"
        "    attach_conn = AttachInputConn(sock_path)\n"
        "    attach_conn.connect()\n"
        '    attach_conn.send_key(b"N")\n'
    )
    rogue_tree = ast.parse(rogue_src)
    violations = _send_violations(rogue_tree, allowed_verbs={"status"}, allowed=_is_allowlisted_attach_site)
    assert violations, (
        "the allowlisted shape (AttachInputConn construction + attach_conn.send_key) "
        "reached from a function OTHER than _attempt_attach/_run_play must still trip "
        "the guard -- this is the direct regression pin for the confirmed hole"
    )


# ---------------------------------------------------------------------------
# 3 & 4. PlayShellScreen -- the concrete spectate-state-bearing class
#    (PWO-055, lane A, landed mid-flight during this dispatch: `cockpit.
#    control_seat` + `PlayShellScreen.spectating: bool`, defaulting True
#    "since this screen has no send path at all" -- screens.py's own
#    updated docstring). This is the file/class the WO's own trap warning
#    is about. Real today (screens.py exists with substantial content;
#    the scanner's soundness is proven independently above) -- currently
#    clean because lane A's own PWO-055 states that invariant explicitly,
#    not because nothing was scanned.
# ---------------------------------------------------------------------------


def test_play_shell_screen_class_has_no_send_capable_call_or_symbol():
    src = Path(inspect.getsourcefile(screens_mod)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PlayShellScreen"
    )
    violations = _send_violations(cls, allowed_verbs=set())
    assert not violations, f"PlayShellScreen must stay send-free; found: {violations}"


def test_screens_module_has_no_send_capable_call_or_symbol():
    """Belt-and-suspenders beyond the class-scoped guard above: also bans
    a module-level helper function in screens.py (outside the class body)
    from ever becoming a send path reachable from the spectate cockpit."""
    src = Path(inspect.getsourcefile(screens_mod)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    violations = _send_violations(tree, allowed_verbs=set())
    assert not violations, f"screens.py must stay send-free; found: {violations}"


def test_play_shell_screen_entry_state_is_app_hold_and_owns_no_send_path(monkeypatch):
    """THE CANARY -- re-justified, deliberately NOT silenced (WO-ENTRY-APP-
    CHIP, hub-ruled). It fired correctly on the very change it was built
    to catch; this docstring records why the flip is legitimate, and the
    assertions below keep their teeth.

    RENAMED from ``test_play_shell_screen_defaults_to_spectating``, whose
    premise was stale twice over: it asserted ``spectating`` is ``True``,
    "the ONLY value reachable today (no PWO-056 attach path exists yet to
    ever flip it)". PWO-056 shipped, and ``app.py::_run_play`` has been
    writing both seat flags since.

    THE CONTRACT (unchanged in substance): a flipped client-state default
    is legitimate ONLY while it does not outrun the gated send path. The
    gated path is exactly one adjudicated site -- ``attach_conn.send_key(
    ...)`` in ``app.py::_run_play``, the sole shape
    ``_is_allowlisted_attach_site`` above excuses, and reachable only
    AFTER ``_attempt_attach`` obtains the daemon's Human control lock
    (``session/control_lock.py::take_human``). Every other send-capable
    shape still trips the AST guards above.

    WHY THE FLIP IS LEGITIMATE NOW, on all three legs:
      1. Owner-ruled, and canon already prescribed it --
         ``canon/surfaces/mode-line-and-teach-controls.md:39`` ("Default
         when the client runs = App/autopilot"), ratified in ADR-002. The
         entry state is App-hold: both flags literally ``False``,
         mirroring the daemon's own ``session/control_lock.py:59``
         ``self._mode = MODE_APP``.
      2. The send path was ALREADY adjudicated by PWO-056 and is
         unchanged -- this WO adds no new send-capable shape, no new wire
         verb, and no new call site.
      3. App-hold is a strictly READ-ONLY client state, exactly as
         Spectate was. Neither flag grants send: the ability to send comes
         from holding ``attach_conn``, which only a human Ctrl-A keypress
         can obtain. That is what the assertions below actually verify.

    TEETH -- what still makes this the first thing to go red:
      * either seat flag changing at entry, so a future silent re-flip
        (in EITHER direction) must come back through this docstring;
      * the class gaining a send-capable attribute on the instance -- a
        runtime check the source-level AST guards above cannot make;
      * and, the load-bearing one, the entry instance coming to OWN any
        object that is itself send-capable. A change that handed the
        cockpit a live attach connection at construction would grant send
        WITHOUT adding a send verb to this class, sailing past every AST
        guard in this file. That is precisely "a flipped default
        outrunning the gated send path", and it goes red here."""
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = ProfileRow(
        name="alpha", handle="Alpha", server="demo-a", host="demo-a.example", game_letter="B",
    )

    class _NullWin:
        def getmaxyx(self):
            return (40, 160)

    screen = PlayShellScreen(_NullWin(), profile)

    # App-hold: the entry state, mirroring daemon MODE_APP.
    assert screen.spectating is False
    assert screen.attached is False

    # No send-capable symbol ON the instance -- the runtime counterpart of
    # the source-level AST guards above.
    for verb in ("send", "send_raw", "do", "send_key"):
        assert not hasattr(screen, verb), f"PlayShellScreen grew a {verb!r} attribute"

    # And nothing the entry instance OWNS is send-capable -- no live wire
    # handle may exist before the human's own Ctrl-A takes the Human lock.
    for name, value in vars(screen).items():
        for verb in ("send_key", "send_raw"):
            assert not hasattr(value, verb), (
                f"entry-state attribute {name!r} owns a {verb!r} -- App-hold "
                f"must grant no send path; only a human Ctrl-A may."
            )


# ---------------------------------------------------------------------------
# 5. WatchFeed -- D5 spectator-only "no send/do API of any kind" is a
#    prose contract in the module docstring today; this is its structural
#    proof.
# ---------------------------------------------------------------------------


def test_watchfeed_module_has_no_send_capable_call_or_symbol():
    src = Path(inspect.getsourcefile(watchfeed_mod)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    violations = _send_violations(tree, allowed_verbs=set())
    assert not violations, f"watchfeed.py must never send; found: {violations}"


# ---------------------------------------------------------------------------
# 6. Every file under tw2002_aiclient/cockpit/ -- this WO's own file-
#    ownership section names cockpit/*.py as lane A's home for any new
#    spectate-state module, so scanning the whole package directory is a
#    broader, name-independent net than guessing lane A's exact symbol
#    names (picks up control_seat.py automatically, and any future
#    sibling module the same way).
# ---------------------------------------------------------------------------


def test_cockpit_package_has_no_send_capable_call_or_symbol():
    cockpit_dir = Path(inspect.getsourcefile(cockpit_pkg)).resolve().parent
    py_files = sorted(p for p in cockpit_dir.glob("*.py"))
    assert py_files, "expected cockpit/*.py source files to scan -- test setup is broken"
    all_violations = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        all_violations.extend(f"{path.name}: {v}" for v in _send_violations(tree, allowed_verbs={"status"}))
    assert not all_violations, f"cockpit/*.py must stay send-free (or status-only); found: {all_violations}"


# ---------------------------------------------------------------------------
# Behavioral proof: actually DRIVE app._run_play() against fake transports
# for BOTH wire surfaces it touches, and record every write into ONE
# shared log. The AST guards above prove the SOURCE has no send-capable
# call sites; this proves the RUNTIME agrees -- with the log captured (not
# a bare "assert wire == []"), a future write shows up as new DATA in the
# log rather than as an absence a too-aggressively-stubbed harness could
# render indistinguishable from "nothing happened because I mocked too
# much away" -- the exact shape of trap this WO warns about.
# ---------------------------------------------------------------------------


class _RecordingTransport:
    """Fake WatchFeed transport: records every ``sendall()``; the reader
    thread sees immediate EOF (no events needed for this proof -- only
    the WRITE side matters)."""

    def __init__(self, log):
        self._log = log

    def sendall(self, data):
        self._log.append(("wire_write", data))

    def makefile(self, mode):
        return _ImmediateEOFFile()

    def shutdown(self, how):
        return None

    def close(self):
        return None


class _ImmediateEOFFile:
    def readline(self):
        return b""

    def close(self):
        return None


class _ScriptedStdscr:
    """Minimal curses double -- exactly the methods ``screens.py``'s
    ``draw()`` and ``app.py``'s loop actually call on ``stdscr`` (verified
    by grep before writing this: erase/getmaxyx/attron/attroff/box/
    addstr/refresh/getch/timeout -- no ``addnstr``, no sub-windows;
    ``cockpit/draw.py`` only ever calls ``win.addstr``/``win.getmaxyx`` on
    the window it's handed). Full-tier size (40x160, the same constant
    ``tests/test_cockpit_liveness_pty.py`` uses for its own full-tier
    proof) so GOALS/right_gutter/control_strip are all present --
    ``status_provider()`` genuinely polls once per draw, giving the log
    real ``status_call`` entries to assert on rather than none."""

    def __init__(self, keys):
        self._keys = list(keys)

    def getch(self):
        return self._keys.pop(0) if self._keys else -1

    def timeout(self, _ms):
        return None

    def erase(self):
        return None

    def getmaxyx(self):
        return (40, 160)

    def attron(self, *_a, **_k):
        return None

    def attroff(self, *_a, **_k):
        return None

    def box(self):
        return None

    def addstr(self, *_a, **_k):
        return None

    def refresh(self):
        return None


def _profile():
    return ProfileRow(
        name="alpha", handle="Alpha", server="demo-a", host="demo-a.example", game_letter="B",
    )


def test_run_play_drives_only_subscribe_and_status_writes(monkeypatch, tmp_path):
    """Drives ``app._run_play()`` end-to-end (several benign keypresses,
    then Esc) against fake transports for both wire surfaces it touches --
    ``WatchFeed``'s raw socket (subscribe) and ``session_cli.send_request``
    (status poll) -- and asserts the shared write-log contains ONLY those
    two kinds of entries, with at least one of each genuinely recorded (so
    this can't pass by accident because the loop never actually ran)."""
    monkeypatch.setenv("TW_RUN_DIR", str(tmp_path))  # isolated -- never run/twd.sock
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    monkeypatch.setattr(
        adapters, "ensure_session",
        lambda *a, **k: EnsureResult(ok=True, classification="main_command"),
    )

    log: list[tuple] = []

    monkeypatch.setattr(
        watchfeed_mod, "_default_connect_fn",
        lambda run_dir: (lambda: _RecordingTransport(log)),
    )

    def _spy_send(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        log.append(("status_call", verb, args_payload))
        return {"ok": True, "connected": True}

    monkeypatch.setattr(session_cli, "send_request", _spy_send)

    # Several arbitrary keys PlayShellScreen.handle_key doesn't map (each a
    # no-op that loops back to another draw()) before Esc -- proves no
    # KEYPRESS triggers a send either, not just that the idle loop stays
    # quiet -- then multiple draw cycles genuinely happen, landing more
    # than one status_call in the log.
    keys = [ord("a"), curses.KEY_UP, ord("7"), 27]
    stdscr = _ScriptedStdscr(keys)

    result = app._run_play(stdscr, _profile())

    assert result == "back"

    wire_writes = [e for e in log if e[0] == "wire_write"]
    assert len(wire_writes) == 1, (
        f"expected exactly one WatchFeed wire write (the subscribe line); got {wire_writes}"
    )
    assert json.loads(wire_writes[0][1].decode("utf-8")) == {"verb": "subscribe", "args": {}}

    status_calls = [e for e in log if e[0] == "status_call"]
    assert status_calls, "expected at least one status_provider() poll -- got none; test isn't exercising the draw loop"
    assert all(c[1] == "status" for c in status_calls), f"a non-status verb reached send_request: {status_calls}"

    # The whole point: a THIRD kind of log entry (any new write shape a
    # future violation would add) fails this -- a stronger signal than a
    # bare "assert wire == []" that a too-aggressively-stubbed harness
    # could satisfy by accident.
    assert {e[0] for e in log} == {"wire_write", "status_call"}, f"unexpected wire traffic kind(s) in log: {log}"
