"""Shared Layer-B pty + pyte helpers (WO-P3-HARNESS-REHAB D1 lane 2).

Extracted from the archive/pre-rebirth patterns in ``test_spectate_app.py``
and ``test_interactive_app.py`` so Phase-3 frame WOs can write
``tw2002_aiclient``-only proofs without depending on banked ``twclient``
test modules.

Scope (thin harness only):
  - winsize + openpty spawn/capture
  - ordered mid-run keystroke injection
  - pyte replay → grid / find_text / cell attrs
  - opt-in controlling-tty claim for live-resize / SIGWINCH proofs

Out of scope (deliberate):
  - cockpit chrome product UI
  - ``frame_layout`` geometry port
  - credentials / secrets
  - live ``run/twd.sock`` attachment

Skip-guard for curses-in-pty suites stays in ``tests.conftest.pty_curses_supported``
(functional probe already greenfield). Re-exported here for one-stop imports.

Controlling TTY / SIGWINCH (WO-P3-PTY-CTTY)
-------------------------------------------
Default spawn keeps ``start_new_session=True`` and does **not** claim the
pty slave as the child's controlling terminal. Existing 030/cockpit Layer-B
suites rely on that path and must stay unchanged.

Live-resize tests that need ``SIGWINCH`` when the parent calls
``set_winsize(master_fd, …)`` must opt in::

    capture_pty(..., claim_ctty=True)
    capture_pty_with_keys(..., claim_ctty=True)

That path still uses ``start_new_session=True`` (session leader), then a
``preexec_fn`` that ``ioctl(0, TIOCSCTTY)`` so the slave becomes the
controlling tty and kernel window-size changes deliver ``SIGWINCH``.
"""

from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import termios
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pyte

# Genuine SGR color-SET (not bare reset / bold alone) — archive
# test_spectate_app._COLOR_SET_SGR_RE. Useful for Layer-B color proofs.
COLOR_SET_SGR_RE = re.compile(rb"\x1b\[[0-9;]*(?:3[0-7]|4[0-7]|9[0-7]|10[0-7])m")

# Default detach for spectate-style loops (``q``). Attach uses Ctrl-] —
# pass ``detach_keys=bytes([29])`` instead.
DEFAULT_DETACH = b"q"


def _claim_controlling_tty(slave_fd: int) -> None:
    """Make ``slave_fd`` this process's controlling terminal (resize opt-in).

    Default ``capture_pty*`` uses ``start_new_session=True`` alone — the child
    is session-leader-ish via Popen but never claims the pty as ctty, so
    ``SIGWINCH`` from a later ``TIOCSWINSZ`` on the master is never delivered.
    Call this from ``preexec_fn`` when ``claim_ctty=True``.
    """
    os.setsid()
    # TIOCSCTTY: claim controlling tty. Value is platform-constant; fcntl
    # ioctl with arg 0 is the usual Unix form.
    try:
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
    except (OSError, AttributeError):
        # AttributeError if TIOCSCTTY missing; OSError if already claimed /
        # unsupported — leave session without ctty (same as default path).
        pass


def set_winsize(fd: int, rows: int, cols: int) -> None:
    """``TIOCSWINSZ`` on a pty slave — required before curses initscr sees size."""
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def capture_pty(
    argv: Sequence[str],
    stop_condition: Callable[[bytes], bool],
    *,
    timeout: float = 10.0,
    rows: int = 24,
    cols: int = 80,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    detach_keys: bytes = DEFAULT_DETACH,
    drain_after_s: float = 5.0,
    claim_ctty: bool = False,
) -> bytes:
    """Spawn ``argv`` in a pty; stream stdout until ``stop_condition`` or timeout.

    Always attempts ``detach_keys`` before teardown (spectate ``q``, attach
    Ctrl-], etc.). Drains the master while waiting so a clean child exit
    isn't wedged on a full pty buffer (archive lesson from confirm-gate
    RECORD_PATH flows).

    ``claim_ctty=False`` (default): ``start_new_session=True`` only — preserves
    existing 030/cockpit Layer-B behavior (no SIGWINCH delivery).

    ``claim_ctty=True``: child ``setsid`` + ``TIOCSCTTY`` so a later
    ``set_winsize(master_fd, …)`` can deliver ``SIGWINCH`` for live-resize
    proofs. Opt in only from resize tests.
    """
    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    child_env = dict(os.environ if env is None else env)
    child_env.setdefault("TERM", "xterm")

    popen_kwargs: dict[str, Any] = {
        "stdin": slave_fd,
        "stdout": slave_fd,
        "stderr": slave_fd,
        "cwd": str(cwd) if cwd is not None else None,
        "env": child_env,
    }
    if claim_ctty:
        # Slave must stay open in the child until ioctl; pass fd via closure.
        def _preexec() -> None:
            _claim_controlling_tty(slave_fd)

        popen_kwargs["preexec_fn"] = _preexec
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(list(argv), **popen_kwargs)
    os.close(slave_fd)

    captured = b""
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.5)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
            if stop_condition(captured):
                break
    finally:
        try:
            if detach_keys:
                os.write(master_fd, detach_keys)
        except OSError:
            pass
        captured += _drain_until_exit(proc, master_fd, drain_after_s)
        _close_master(master_fd)
    return captured


def capture_pty_with_keys(
    argv: Sequence[str],
    steps: Sequence[tuple[bytes, bytes] | None],
    stop_condition: Callable[[bytes], bool],
    *,
    timeout: float = 10.0,
    rows: int = 24,
    cols: int = 80,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    detach_keys: bytes = DEFAULT_DETACH,
    drain_after_s: float = 5.0,
    claim_ctty: bool = False,
) -> bytes:
    """Like ``capture_pty``, plus ordered mid-run keystroke injection.

    Each step is ``(marker_bytes, keys_bytes)``: once ``marker_bytes`` first
    appears in the captured stream, write ``keys_bytes`` once. Steps fire
    strictly in order (step N never before step N-1). ``None`` entries are
    skipped. Mirrors archive ``_run_fake_spectate_and_type_in_pty`` /
    ``test_control_panel._drive_pty``.

    ``claim_ctty`` — same contract as ``capture_pty`` (default off).
    """
    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    child_env = dict(os.environ if env is None else env)
    child_env.setdefault("TERM", "xterm")

    popen_kwargs: dict[str, Any] = {
        "stdin": slave_fd,
        "stdout": slave_fd,
        "stderr": slave_fd,
        "cwd": str(cwd) if cwd is not None else None,
        "env": child_env,
    }
    if claim_ctty:
        def _preexec() -> None:
            _claim_controlling_tty(slave_fd)

        popen_kwargs["preexec_fn"] = _preexec
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(list(argv), **popen_kwargs)
    os.close(slave_fd)

    pending = [s for s in steps if s is not None]
    fired = [False] * len(pending)
    captured = b""
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.3)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
            for i, (marker, keys) in enumerate(pending):
                if fired[i]:
                    continue
                if i > 0 and not fired[i - 1]:
                    break
                if marker in captured:
                    try:
                        os.write(master_fd, keys)
                    except OSError:
                        pass
                    fired[i] = True
            if stop_condition(captured):
                break
    finally:
        try:
            if detach_keys:
                os.write(master_fd, detach_keys)
        except OSError:
            pass
        captured += _drain_until_exit(proc, master_fd, drain_after_s)
        _close_master(master_fd)
    return captured


def pyte_screen(captured: bytes, rows: int, cols: int) -> pyte.Screen:
    """Replay raw pty bytes through pyte into a ``rows``×``cols`` screen.

    Returns the live ``pyte.Screen`` — use ``.display`` for text,
    ``.buffer[r][c].fg`` / ``.reverse`` / ``.bold`` for cell attrs,
    ``.cursor.y/x`` for caret proofs. UTF-8 with replacement (curses
    chrome under a UTF-8 locale).
    """
    screen = pyte.Screen(cols, rows)
    stream = pyte.Stream(screen)
    stream.feed(captured.decode("utf-8", errors="replace"))
    return screen


def pyte_grid(captured: bytes, rows: int, cols: int) -> list[str]:
    """Plain-text rows from ``pyte_screen(...).display``."""
    return list(pyte_screen(captured, rows, cols).display)


def find_text(grid: Sequence[str], needle: str) -> tuple[int, int] | None:
    """``(row, col)`` of the first ``needle`` in a pyte grid, or ``None``."""
    for r, row_text in enumerate(grid):
        c = row_text.find(needle)
        if c != -1:
            return r, c
    return None


def cell_at(screen: pyte.Screen, row: int, col: int) -> Any:
    """Convenience: ``screen.buffer[row][col]`` (pyte Char with .fg/.bold/…)."""
    return screen.buffer[row][col]


# Underscore aliases — drop-in for archive-local ``_set_winsize`` / ``_pyte_*``.
_set_winsize = set_winsize
_capture_pty = capture_pty
_pyte_screen = pyte_screen
_pyte_grid = pyte_grid
_find_text = find_text


def _drain_until_exit(proc: subprocess.Popen, master_fd: int, drain_after_s: float) -> bytes:
    """Drain master while waiting for child exit; kill if still alive."""
    extra = b""
    drain_deadline = time.monotonic() + drain_after_s
    while time.monotonic() < drain_deadline and proc.poll() is None:
        ready, _, _ = select.select([master_fd], [], [], 0.2)
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            extra += chunk
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    return extra


def _close_master(master_fd: int) -> None:
    try:
        os.close(master_fd)
    except OSError:
        pass


# Re-export skip-guard without importing conftest at module load (conftest
# pulls heavier session fixtures). Lazy so ``import tests.pty_helpers`` stays
# light and twclient-free.
def pty_curses_supported() -> bool:
    """Functional curses-in-pty probe — delegates to ``tests.conftest``."""
    from tests.conftest import pty_curses_supported as _probe

    return bool(_probe())
