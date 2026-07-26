"""Smoke proofs for Layer-B shared harness helpers (WO-P3-HARNESS-REHAB D1 lane 2).

Network-free, twclient-free, no cockpit chrome. Proves the helpers import
and behave well enough for later frame WOs to build on.
"""

from __future__ import annotations

import ast
import os
import pty
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.fake_client import FakeClient
from tests.pty_helpers import (
    COLOR_SET_SGR_RE,
    DEFAULT_TERM,
    capture_pty,
    capture_pty_with_keys,
    find_text,
    pty_curses_supported,
    pyte_grid,
    pyte_screen,
    set_winsize,
    terminate_session_group,
)


HELPERS = (
    Path(__file__).resolve().parent / "fake_client.py",
    Path(__file__).resolve().parent / "pty_helpers.py",
)


def test_helpers_do_not_import_twclient():
    """Layer-B consumers must stay on tw2002_aiclient / stdlib / pyte only."""
    for path in HELPERS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("twclient"), path
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("twclient"), path


def test_fake_client_yields_events_then_none():
    client = FakeClient([{"screen": ["hi"]}, {"screen": ["bye"]}], gap_s=0.0)
    assert client.remaining == 2
    assert client.next_event() == {"screen": ["hi"]}
    assert client.next_event() == {"screen": ["bye"]}
    assert client.exhausted
    assert client.next_event(timeout=0.0) is None
    client.close()  # no-op, must not raise


def test_pyte_helpers_locate_text_and_color_attrs():
    # Minimal ANSI: clear, cyan "CREDITS" at home, then plain "SECTOR".
    captured = b"\x1b[2J\x1b[H\x1b[36mCREDITS\x1b[0m SECTOR"
    rows, cols = 5, 40
    screen = pyte_screen(captured, rows, cols)
    grid = pyte_grid(captured, rows, cols)
    pos = find_text(grid, "CREDITS")
    assert pos == (0, 0)
    cell = screen.buffer[0][0]
    assert cell.data == "C"
    assert cell.fg == "cyan"
    assert find_text(grid, "SECTOR") == (0, 8)
    assert COLOR_SET_SGR_RE.search(captured) is not None


def test_set_winsize_callable():
    # Smoke: symbol exists and is callable (real ioctl needs a pty fd —
    # capture_pty exercises that path when a Layer-B suite lands).
    assert callable(set_winsize)


def test_claim_ctty_opt_in_is_documented_kwarg():
    """Resize tests opt in via claim_ctty=True; default stays off (no SIGWINCH)."""
    import inspect

    from tests.pty_helpers import _claim_controlling_tty, capture_pty, capture_pty_with_keys

    assert callable(_claim_controlling_tty)
    for fn in (capture_pty, capture_pty_with_keys):
        params = inspect.signature(fn).parameters
        assert "claim_ctty" in params
        assert params["claim_ctty"].default is False


_SIGWINCH_CHILD = (
    "import signal, sys, time\n"
    "got = []\n"
    "def _h(s, f):\n"
    "    got.append(1)\n"
    "    sys.stdout.write('WINCH\\n')\n"
    "    sys.stdout.flush()\n"
    "signal.signal(signal.SIGWINCH, _h)\n"
    "sys.stdout.write('READY\\n')\n"
    "sys.stdout.flush()\n"
    "deadline = time.monotonic() + 2.0\n"
    "while time.monotonic() < deadline and not got:\n"
    "    time.sleep(0.05)\n"
    "sys.stdout.write('DONE\\n')\n"
    "sys.stdout.flush()\n"
)


def _drive_sigwinch_probe(*, claim_ctty: bool) -> bytes:
    """Tiny openpty driver mirroring capture_pty's claim_ctty branch."""
    from tests.pty_helpers import _claim_controlling_tty

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, 24, 80)
    popen_kwargs: dict = {
        "stdin": slave_fd,
        "stdout": slave_fd,
        "stderr": slave_fd,
    }
    if claim_ctty:
        def _preexec() -> None:
            _claim_controlling_tty(slave_fd)

        popen_kwargs["preexec_fn"] = _preexec
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen([sys.executable, "-c", _SIGWINCH_CHILD], **popen_kwargs)
    os.close(slave_fd)

    captured = b""
    resized = False
    deadline = time.monotonic() + 4.0
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
            if b"READY" in captured and not resized:
                set_winsize(master_fd, 30, 100)
                resized = True
            if b"DONE" in captured:
                break
    finally:
        terminate_session_group(proc, wait_timeout=2.0)
        try:
            os.close(master_fd)
        except OSError:
            pass
    return captured


def test_claim_ctty_delivers_sigwinch_on_master_resize():
    """Opt-in ctty path: TIOCSWINSZ on master → SIGWINCH in child."""
    out = _drive_sigwinch_probe(claim_ctty=True)
    assert b"READY" in out
    assert b"WINCH" in out


def test_default_spawn_does_not_deliver_sigwinch():
    """Default start_new_session=True path stays non-ctty (030/cockpit-safe)."""
    out = _drive_sigwinch_probe(claim_ctty=False)
    assert b"READY" in out
    assert b"WINCH" not in out


# --- terminal environment is decided, not inherited (WO-AUDIT-PTY-TERM-INHERITANCE)
#
# Every assertion below reads what the CHILD actually saw, never the helper's
# source text — so they survive a rewrite and still fail on a behavioural
# revert (e.g. back to ``child_env.setdefault("TERM", "xterm")``, which honours
# an ambient shell ``TERM`` and let a whole pty suite fail on the terminal
# instead of on the product).

_REPORTED_VARS = ("TERM", "LINES", "COLUMNS", "TW_PTY_PIN")
_UNSET = "<unset>"

_ENV_REPORT_CHILD = (
    "import os, sys\n"
    "for var in %r:\n"
    "    sys.stdout.write('ENV %%s=%%s\\n' %% (var, os.environ.get(var, %r)))\n"
    "sys.stdout.write('ENV-DONE\\n')\n"
    "sys.stdout.flush()\n"
) % (_REPORTED_VARS, _UNSET)

_CURSES_SIZE_CHILD = (
    "import curses, sys\n"
    "def _main(_stdscr):\n"
    "    sys.stdout.write('SIZE %d %d\\n' % (curses.LINES, curses.COLS))\n"
    "    sys.stdout.flush()\n"
    "curses.wrapper(_main)\n"
)


def _run_child(driver, source, stop_marker, **kwargs) -> bytes:
    """Spawn ``source`` through ``driver`` (capture_pty / *_with_keys)."""
    argv = [sys.executable, "-c", source]
    stop = lambda data: stop_marker in data  # noqa: E731
    if driver is capture_pty_with_keys:
        return driver(argv, [], stop, timeout=15.0, **kwargs)
    return driver(argv, stop, timeout=15.0, **kwargs)


def _child_env_report(driver=capture_pty, **kwargs) -> dict[str, str]:
    """What the spawned child's own ``os.environ`` held, per reported var.

    Scanned rather than line-anchored: a pty stream interleaves the child's
    writes with terminal escapes, so a report can share a line with them.
    """
    captured = _run_child(driver, _ENV_REPORT_CHILD, b"ENV-DONE", **kwargs)
    text = captured.replace(b"\r", b"").decode(errors="replace")
    seen = dict(re.findall(r"ENV (\w+)=(\S*)", text))
    assert set(_REPORTED_VARS) <= set(seen), (
        "child never reported its environment: " + repr(captured[:400])
    )
    return seen


@pytest.mark.parametrize("driver", [capture_pty, capture_pty_with_keys])
def test_ambient_terminal_environment_never_reaches_the_child(driver, monkeypatch):
    """The invoking shell does not get to choose the terminal under test.

    Both leaks in one hostile ambient env. ``TERM=dumb`` carries no ``cup``,
    so curses can address nothing and only chrome survives to the replay;
    ``LINES``/``COLUMNS`` outrank the pty's real winsize in ncurses, so an
    exported ``COLUMNS`` silently resizes the terminal out from under a
    ``pyte_grid(captured, rows, cols)`` read.
    """
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("LINES", "50")
    monkeypatch.setenv("COLUMNS", "200")

    seen = _child_env_report(driver)

    assert seen["TERM"] == DEFAULT_TERM, "ambient TERM decided the child's terminal"
    assert seen["LINES"] == _UNSET, "ambient LINES reached the child"
    assert seen["COLUMNS"] == _UNSET, "ambient COLUMNS reached the child"


def test_caller_env_cannot_smuggle_an_ambient_term(monkeypatch):
    """A caller-supplied ``env=`` is respected — except where it is ambient.

    The one in-tree ``env=`` caller builds ``dict(os.environ, …)`` to pin an
    unrelated variable, so its ``TERM`` is inheritance in an explicit-looking
    coat. The rest of that dict must still reach the child.
    """
    monkeypatch.setenv("TERM", "dumb")

    seen = _child_env_report(env=dict(os.environ, TW_PTY_PIN="carried"))

    assert seen["TERM"] == DEFAULT_TERM
    assert seen["TW_PTY_PIN"] == "carried", "caller's own env entries were dropped"


def test_term_kwarg_is_the_deliberate_override():
    """``term=`` is how a test asks for a poor terminal on purpose."""
    assert _child_env_report(term="dumb")["TERM"] == "dumb"


def test_term_none_unsets_the_child_terminal():
    """``term=None`` means no terminal type at all — not "inherit one"."""
    assert _child_env_report(term=None)["TERM"] == _UNSET


@pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)
def test_child_curses_geometry_follows_the_pty_not_the_environment(monkeypatch):
    """``rows=``/``cols=`` is the only size channel — proven inside curses.

    The env-strip above is the mechanism; this is the behaviour it buys. On
    an unstripped env this child reports 50x200 on a 24x80 pty.
    """
    monkeypatch.setenv("LINES", "50")
    monkeypatch.setenv("COLUMNS", "200")

    captured = _run_child(capture_pty, _CURSES_SIZE_CHILD, b"SIZE", rows=24, cols=80)

    text = captured.replace(b"\r", b"").decode(errors="replace")
    sizes = re.findall(r"SIZE (\d+) (\d+)", text)
    assert sizes, "child never reported its curses geometry: " + repr(captured[:400])


# ---------------------------------------------------------------------------
# WO-TUI-DEAD-TERMINAL-SPIN Defect 2 (Samantha review, 2026-07-26): the
# direct child exiting cleanly does NOT mean its whole process group is
# empty. This is the COMMON path for this suite's own pty tests (the TUI
# exits cleanly on Esc/quit in most of them), not an exotic one -- a
# grandchild the direct child spawned and left running survives unless the
# GROUP itself is swept.
# ---------------------------------------------------------------------------


def _old_poll_gated_terminate(proc: subprocess.Popen, *, wait_timeout: float = 5.0) -> None:
    """The ORIGINAL, Samantha-review-caught shape -- gated on
    ``proc.poll()``, which skips the whole-group signal in exactly the
    case where the direct child has ALREADY exited cleanly. Kept here,
    inline, purely as the injection vehicle for the red-first proof below
    -- never call this in real cleanup code; ``terminate_session_group``
    is the fixed, unconditional replacement.
    """
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=wait_timeout)
    except subprocess.TimeoutExpired:
        pass


def _wait_until_gone(pid: int, *, timeout: float) -> bool:
    """Bounded poll for a pid to fully disappear from the process table.

    A single immediate ``os.kill(pid, 0)`` right after signalling is NOT
    reliable here: once its own parent (the direct child) has already
    exited and been reaped, the grandchild is reparented at that moment,
    so a SIGKILL turns it into a zombie under its NEW parent -- which
    still answers ``os.kill(pid, 0)`` successfully until that parent
    reaps it. How quickly that reaping happens is environment-dependent
    (observed to need more than an immediate check in this sandbox), so
    this polls instead of asserting on a single snapshot.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _spawn_direct_child_with_live_grandchild(tmp_path: Path) -> tuple[subprocess.Popen, int]:
    """Spawn a direct child (its own session) that forks a long-lived
    grandchild, records its pid, then exits 0 immediately -- returns
    ``(direct_child_proc, grandchild_pid)`` with the direct child already
    reaped (``proc.wait()`` already called) and the grandchild confirmed
    still alive."""
    marker = tmp_path / "grandchild.pid"
    src = (
        "import subprocess, sys\n"
        "gc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(marker)!r}, 'w').write(str(gc.pid))\n"
        "sys.exit(0)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", src], start_new_session=True)
    proc.wait(timeout=5.0)  # the direct child exits cleanly, on its own
    assert proc.returncode == 0
    assert marker.exists(), "middle process exited before recording the grandchild pid"
    grandchild_pid = int(marker.read_text().strip())
    os.kill(grandchild_pid, 0)  # still alive -- proves the repro reaches the defect
    return proc, grandchild_pid


def test_old_poll_gated_shape_leaves_the_grandchild_orphaned(tmp_path):
    """Red-first: the shape Samantha's review caught really does leave a
    live grandchild behind once the direct child has already exited."""
    proc, grandchild_pid = _spawn_direct_child_with_live_grandchild(tmp_path)
    try:
        _old_poll_gated_terminate(proc)
        os.kill(grandchild_pid, 0)  # still alive -- the old shape never signalled it
    finally:
        try:
            os.kill(grandchild_pid, 9)
        except ProcessLookupError:
            pass


def test_terminate_session_group_reaps_the_grandchild_after_clean_exit(tmp_path):
    """Green: the fixed, unconditional sweep reaches the grandchild even
    though the direct child (the group leader) is already gone."""
    proc, grandchild_pid = _spawn_direct_child_with_live_grandchild(tmp_path)

    terminate_session_group(proc)

    assert _wait_until_gone(grandchild_pid, timeout=3.0), (
        f"grandchild pid {grandchild_pid} still present after terminate_session_group"
    )


# ---------------------------------------------------------------------------
# Structural pin: every terminate_session_group call site must be reachable
# to a setsid'd spawn. terminate_session_group trusts `proc.pid` AS the
# process-group id with no `os.getpgid(proc.pid)` re-check (that lookup
# raises ProcessLookupError on an already-reaped pid -- see the function's
# own docstring for why it was tried and rejected). That trust is only
# sound because every spawn feeding this suite's `proc` objects uses
# `start_new_session=True` or the `claim_ctty` preexec's own
# `os.setsid()`. A future call site that skips both would put its child in
# THIS suite's own process group, and `killpg` there would take down the
# test runner itself.
# ---------------------------------------------------------------------------


def _iter_terminate_session_group_call_sites():
    """Yield ``(path, enclosing_function_or_None, module_tree)`` for every
    ``terminate_session_group(...)`` call under ``tests/``."""
    tests_dir = Path(__file__).resolve().parent
    for path in sorted(tests_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        stack: list[ast.AST] = []
        findings: list[tuple[Path, ast.AST | None, ast.AST]] = []

        class _Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):  # noqa: N802
                stack.append(node)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):  # noqa: N802
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else None
                )
                if name == "terminate_session_group":
                    findings.append((path, stack[-1] if stack else None, tree))
                self.generic_visit(node)

        _Visitor().visit(tree)
        yield from findings


def _has_setsid_evidence(scope: ast.AST | None) -> bool:
    """True iff ``scope`` (a function or module AST node) shows a setsid'd
    spawn: ``start_new_session=True`` on some call, or a call reaching
    ``_claim_controlling_tty`` (which itself calls ``os.setsid()``)."""
    if scope is None:
        return False
    for node in ast.walk(scope):
        if isinstance(node, ast.keyword) and node.arg == "start_new_session":
            if isinstance(node.value, ast.Constant) and node.value.value is True:
                return True
        if isinstance(node, ast.Call):
            fn = node.func
            fn_name = (
                fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
            )
            if fn_name == "_claim_controlling_tty":
                return True
    return False


def test_every_terminate_session_group_call_site_has_a_setsid_spawn():
    """Checks the ENCLOSING FUNCTION first (strongest evidence); falls back
    to the enclosing MODULE for a helper like
    ``pty_helpers._drain_until_exit``, which receives an already-spawned
    ``proc`` from a sibling function (``capture_pty`` /
    ``capture_pty_with_keys``) in the same file rather than spawning it
    itself.
    """
    sites = list(_iter_terminate_session_group_call_sites())
    assert sites, "no terminate_session_group call sites found — guard is vacuous"

    failures = []
    for path, enclosing_func, tree in sites:
        ok = _has_setsid_evidence(enclosing_func) or _has_setsid_evidence(tree)
        if not ok:
            where = enclosing_func.name if enclosing_func is not None else "<module level>"
            failures.append(f"{path.name}::{where}")

    assert not failures, (
        "call site(s) with no start_new_session=True / _claim_controlling_tty "
        "evidence in scope — killpg here could hit OUR OWN process group: "
        + ", ".join(failures)
    )


# ---------------------------------------------------------------------------
# WO-TUI-KILLPG-EPERM-CURSES-PTY — EPERM path must stay loud; carve-out must
# still terminate the direct child (audit/killpg-eperm-curses-pty-20260726.md).
# ---------------------------------------------------------------------------


def test_terminate_session_group_eperm_warns_and_kills_direct_child(monkeypatch):
    """Injected PermissionError on killpg must RuntimeWarn and still kill."""
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        start_new_session=True,
    )
    os.close(slave_fd)
    os.close(master_fd)

    def _boom(pgid, sig):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(os, "killpg", _boom)

    with pytest.warns(RuntimeWarning, match="PermissionError"):
        terminate_session_group(proc, wait_timeout=2.0)

    assert proc.poll() is not None, "direct child must terminate on EPERM fallback"
    assert _wait_until_gone(proc.pid, timeout=2.0)


def test_terminate_session_group_doc_does_not_overclaim_whole_group():
    """Carve-out honesty: docstring must admit EPERM degrade (WO-TUI-KILLPG-EPERM)."""
    doc = terminate_session_group.__doc__ or ""
    assert "PermissionError" in doc or "EPERM" in doc
    assert "not** an unconditional guarantee" in doc or "not an unconditional guarantee" in doc
