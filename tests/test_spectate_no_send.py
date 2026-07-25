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


def _iter_send_request_calls(node):
    """Every ``Call`` under ``node`` whose func attribute is literally
    named ``send_request`` -- matches ``session_cli.send_request(...)``,
    ``_cli.send_request(...)``, ``self.session_cli.send_request(...)``,
    etc. (the base object's name is deliberately NOT pinned)."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "send_request":
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


def _banned_name_hits(node):
    attrs = {
        n.attr for n in ast.walk(node)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load)
    }
    names = {
        n.id for n in ast.walk(node)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    imported = {
        alias.asname or alias.name
        for n in ast.walk(node)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for alias in n.names
    }
    return (attrs | names | imported) & _BANNED_SEND_SYMBOLS


def _send_violations(node, *, allowed_verbs):
    """Every send-capable violation found under ``node`` (a Module,
    ClassDef, or FunctionDef), as human-readable strings. Empty means
    clean."""
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
    hit = _banned_name_hits(node)
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
    violations = _send_violations(fn, allowed_verbs={"status"})
    assert not violations, f"_run_play must stay send-free; found: {violations}"


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
    violations = _send_violations(tree, allowed_verbs={"status"})
    assert not violations, f"app.py must only ever request the read-only 'status' verb; found: {violations}"
    assert any(True for _ in _iter_send_request_calls(tree)), (
        "expected at least one real send_request call site in app.py (the status "
        "poll) -- found none; this test's own setup is broken, not proof of anything"
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


def test_play_shell_screen_defaults_to_spectating(monkeypatch):
    """Ties the AST guards above to the actual state flag they're meant to
    protect: ``spectating`` is ``True`` -- the ONLY value reachable today
    (no PWO-056 attach path exists yet to ever flip it). If a future
    change flips this default without also legitimizing a gated send
    path, this is the first thing that should go red."""
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = ProfileRow(
        name="alpha", handle="Alpha", server="demo-a", host="demo-a.example", game_letter="B",
    )

    class _NullWin:
        def getmaxyx(self):
            return (40, 160)

    screen = PlayShellScreen(_NullWin(), profile)
    assert screen.spectating is True


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
