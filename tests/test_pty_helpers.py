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
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
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
    assert sizes[-1] == ("24", "80")
