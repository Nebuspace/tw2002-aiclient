"""Smoke proofs for Layer-B shared harness helpers (WO-P3-HARNESS-REHAB D1 lane 2).

Network-free, twclient-free, no cockpit chrome. Proves the helpers import
and behave well enough for later frame WOs to build on.
"""

from __future__ import annotations

import ast
import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

from tests.fake_client import FakeClient
from tests.pty_helpers import (
    COLOR_SET_SGR_RE,
    find_text,
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
