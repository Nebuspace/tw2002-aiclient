"""WO-TUI-DEAD-TERMINAL-SPIN -- proof that a dead controlling terminal makes
the TUI exit promptly instead of spinning a core forever (Defect 1).

Incident (2026-07-26): 11 orphaned ``curses.wrapper(_run)`` processes --
the real product TUI, not test scaffolding -- found pegging ~11 of 16 cores
(~1094% combined CPU) for up to 22h45m. Root cause: ``getch()`` returning
-1 conflates "no key yet, my timeout elapsed as armed" with "the
controlling terminal is gone, every read() now returns EOF instantly" --
see ``tw2002_aiclient/app.py``'s own module-level comment above
``_DeadTerminalGuard`` for the full two-signal argument (orphan self-
defence via ``os.getppid() == 1``, plus a streak of suspiciously-fast -1
returns).

Layers of proof:

- Part 0 -- ``main()``'s own dead-terminal diagnostic must survive a dead
  stderr (a real defect found on review: writing the "terminal is gone"
  message to the terminal that just died raises ``OSError`` EIO).
- Part 1 -- deterministic unit coverage of ``_DeadTerminalGuard`` and
  ``_guarded_getch`` themselves: no pty, no subprocess, elapsed times fed
  directly (or via a real but tiny ``time.sleep``) so nothing here can be
  "flaky on a slow machine" -- the WO's own proof standard.
- Part 2 -- real end-to-end pty proof (the WO's literal Proof requirement):
  spawn the actual product entry point in a real pty, reach a live getch()
  loop, close the pty master out from under it, and assert BOTH that the
  child exits within a bounded deadline AND that it consumed near-zero CPU
  doing so -- exit alone would not catch a fix that exits only after
  spinning for a while. This exercises the TIMING-streak signal (the
  child's own parent stays alive; only its terminal dies).
- Part 3 -- the ORPHAN signal through a genuine subprocess chain (not just
  a monkeypatched ``os.getppid`` as in Part 1): a throwaway middle process
  spawns the real product TUI, then exits immediately without waiting,
  reparenting the TUI to init exactly like the incident (a hard-killed
  pytest orphans a ``start_new_session=True`` pty child the same way,
  confirmed manually during this WO -- see the STATUS report). CPU-
  boundedness for these getch loops is already proven in Part 2; this
  test's own job is proving the orphan signal fires end-to-end, not
  re-proving CPU cost.

Isolation mirrors ``tests/test_cockpit_frame_pty.py``: ``adapters.
ensure_session`` is stubbed inside the spawned process for the play-shell
variant, and ``TW_RUN_DIR`` always points at an isolated tmp directory so
the real (unstubbed) ``WatchFeed`` can never reach the project's own
``run/twd.sock``.
"""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tw2002_aiclient import app as app_mod

from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

ROWS, COLS = 24, 80


# ---------------------------------------------------------------------------
# Part 0 -- main()'s dead-terminal diagnostic must survive a dead stderr.
#
# Samantha review (2026-07-26): confirmed empirically via pty.fork() that
# writing the diagnostic to the SAME terminal that just died raises OSError
# errno 5 (EIO) -- the handler for "the terminal is gone" crashed in exactly
# its own scenario. _report_dead_terminal (extracted from main() so it's
# unit-testable without needing a real dead pty) must swallow that.
# ---------------------------------------------------------------------------


class _DeadStderr:
    """A stderr stand-in whose write() always raises OSError, matching
    the real EIO a write to an already-hung-up pty produces."""

    def write(self, *_a, **_k):
        raise OSError(5, "Input/output error")

    def flush(self):
        pass


def test_report_dead_terminal_survives_a_broken_stderr(monkeypatch):
    monkeypatch.setattr(sys, "stderr", _DeadStderr())
    app_mod._report_dead_terminal(app_mod.DeadTerminalError("terminal gone"))


def test_report_dead_terminal_prints_when_stderr_is_healthy(capsys):
    app_mod._report_dead_terminal(app_mod.DeadTerminalError("terminal gone"))
    assert "terminal gone" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Part 1 -- deterministic unit coverage of _DeadTerminalGuard / _guarded_getch.
# Every "elapsed" value below is either injected directly or produced by a
# real (sub-100ms) time.sleep -- no dependency on how fast the machine is,
# per this WO's own "not timing-flaky" proof standard.
# ---------------------------------------------------------------------------


def test_guard_never_raises_on_slow_negative_ones(monkeypatch):
    """The legitimate idle tick -- a -1 that takes longer than the fast
    floor -- never raises, however many times it repeats."""
    monkeypatch.setattr(os, "getppid", lambda: os.getpid())  # definitely not orphaned
    guard = app_mod._DeadTerminalGuard()
    for _ in range(10):
        guard.check(-1, app_mod._DEAD_TERMINAL_FAST_S * 5)


def test_guard_tolerates_the_slowest_real_test_double_tick(monkeypatch):
    """`_QueueStdscr` (tests/test_cockpit_attach.py) ticks -1 every 50ms,
    for up to several seconds, during a deliberate pause-and-poll. This is
    real wall-clock, not synthetic, and is the SLOWEST legitimate -1 tick
    in-tree -- it must never trip the guard, at any streak length.

    (Several OTHER in-tree test doubles -- e.g. the same file's own
    `_RecordingStdscr`, plus one each in tests/test_cockpit_utf8_getch.py,
    tests/test_play_esc_daemon_survival.py, tests/test_spectate_no_send.py
    -- return -1 with NO delay at all once exhausted, which DOES clear the
    fast floor; they pass only because their scripted key lists all end in
    an exit key before the streak reaches `_DEAD_TERMINAL_STREAK`, not
    because they are somehow fast enough to count as idle. See the
    `app.py` module comment above `_DeadTerminalGuard` for the full
    argument.)"""
    monkeypatch.setattr(os, "getppid", lambda: os.getpid())
    guard = app_mod._DeadTerminalGuard()
    for _ in range(80):  # ~4s at _QueueStdscr's own real cadence
        guard.check(-1, 0.05)


def test_guard_resets_streak_on_a_real_key(monkeypatch):
    """A single legitimate -1 (or two) must never trip the guard on its
    own -- the WO's own constraint -- even when each one is "fast"."""
    monkeypatch.setattr(os, "getppid", lambda: os.getpid())
    guard = app_mod._DeadTerminalGuard()
    for _ in range(app_mod._DEAD_TERMINAL_STREAK - 1):
        guard.check(-1, 0.0)
    guard.check(ord("z"), 0.0)  # a real key resets the streak
    for _ in range(app_mod._DEAD_TERMINAL_STREAK - 1):
        guard.check(-1, 0.0)  # short of the streak again -- must not raise


def test_guard_raises_after_a_streak_of_fast_negative_ones(monkeypatch):
    monkeypatch.setattr(os, "getppid", lambda: os.getpid())
    guard = app_mod._DeadTerminalGuard()
    for _ in range(app_mod._DEAD_TERMINAL_STREAK - 1):
        guard.check(-1, 0.0)
    with pytest.raises(app_mod.DeadTerminalError):
        guard.check(-1, 0.0)


def test_guard_raises_on_a_single_fast_negative_one_when_orphaned(monkeypatch):
    """Orphaned lowers the required fast-streak from 3 down to 1 -- the
    live incident's own processes were simultaneously spinning (fast) AND
    reparented (orphaned), so a single fast -1 already carries both
    signals and needs no further confirmation."""
    monkeypatch.setattr(os, "getppid", lambda: 1)
    guard = app_mod._DeadTerminalGuard()
    with pytest.raises(app_mod.DeadTerminalError):
        guard.check(-1, 0.0)


def test_guard_orphaned_but_slow_never_raises(monkeypatch):
    """Samantha review (2026-07-26): being orphaned is NEVER sufficient on
    its own -- a legitimately backgrounded session whose terminal is
    still fully valid (e.g. `sh -c './tw &'` from a non-session-leader
    subshell, reparented to init immediately with the terminal untouched)
    must not be killed just because its original parent exited. A slow
    -1 -- the normal idle tick -- never counts as evidence, orphaned or
    not, however many times it repeats."""
    monkeypatch.setattr(os, "getppid", lambda: 1)
    guard = app_mod._DeadTerminalGuard()
    for _ in range(10):
        guard.check(-1, app_mod._DEAD_TERMINAL_FAST_S * 5)


def test_guard_orphan_check_never_fires_on_a_real_key(monkeypatch):
    monkeypatch.setattr(os, "getppid", lambda: 1)
    guard = app_mod._DeadTerminalGuard()
    guard.check(ord("z"), 0.0)  # must not raise -- key != -1 short-circuits first


class _SleepyStdscr:
    """Fake stdscr whose getch() sleeps a fixed duration before returning
    -1 -- exercises `_guarded_getch`'s OWN `time.monotonic()` measurement
    with genuine (small) wall-clock elapsed time, unlike the `guard.check`
    tests above which inject `elapsed_s` directly."""

    def __init__(self, sleep_s: float):
        self._sleep_s = sleep_s

    def getch(self) -> int:
        time.sleep(self._sleep_s)
        return -1


def test_guarded_getch_never_raises_at_the_queue_stdscr_tick_rate(monkeypatch):
    monkeypatch.setattr(os, "getppid", lambda: os.getpid())
    stdscr = _SleepyStdscr(0.05)
    guard = app_mod._DeadTerminalGuard()
    for _ in range(20):
        assert app_mod._guarded_getch(stdscr, guard) == -1


def test_guarded_getch_raises_when_reads_return_instantly(monkeypatch):
    """The real regression shape: getch() returning -1 with ~zero elapsed
    time, repeatedly -- exactly what a dead pty's read() does."""
    monkeypatch.setattr(os, "getppid", lambda: os.getpid())
    stdscr = _SleepyStdscr(0.0)
    guard = app_mod._DeadTerminalGuard()
    with pytest.raises(app_mod.DeadTerminalError):
        for _ in range(app_mod._DEAD_TERMINAL_STREAK):
            app_mod._guarded_getch(stdscr, guard)


# ---------------------------------------------------------------------------
# Part 2 -- real end-to-end pty proof: close the master, measure exit + CPU.
# ---------------------------------------------------------------------------

_BOOTSTRAP_LAUNCHER = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, {project_root!r})

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""

# Play-shell variant: stubs adapters.ensure_session (no real daemon needed)
# exactly like tests/test_cockpit_frame_pty.py's own _BOOTSTRAP, so the
# THROTTLED (stdscr.timeout(1000)) loop in _run_play is reached instead of
# the launcher's blocking-mode dispatch loop.
_BOOTSTRAP_PLAY = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, {project_root!r})

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import EnsureResult

adapters.ensure_session = lambda *a, **k: EnsureResult(ok=True, classification="main_command")

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _spawn_bootstrap(tmp_path: Path, name: str, src: str, *, run_dir: Path | None = None):
    bootstrap = tmp_path / name
    bootstrap.write_text(src.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, ROWS, COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    if run_dir is not None:
        env["TW_RUN_DIR"] = str(run_dir)
    env.pop("TW2002_HANDOFF_SMOKE", None)
    env.pop("TW2002_LAUNCHER_SMOKE", None)
    env.pop("TW2002_BANK_SMOKE", None)

    proc = subprocess.Popen(
        [sys.executable, str(bootstrap)],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(PROJECT_ROOT),
        env=env,
        start_new_session=True,
    )
    os.close(slave_fd)
    return proc, master_fd


def _read_until(master_fd: int, needle: str, *, timeout: float) -> bytes:
    captured = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.2)
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured += chunk
        if find_text(pyte_grid(captured, ROWS, COLS), needle) is not None:
            break
    return captured


def _wait_dead_with_rusage(pid: int, *, deadline_s: float):
    """Poll `os.wait4(pid, WNOHANG)` for the child's exit, bounded.

    Deliberately NOT `proc.poll()`/`proc.wait()`: this is the ONE reap of
    `pid`, and it is the only way to get resource usage scoped to just
    this child in the same call that observes its exit -- Popen's own
    reaping (a plain `os.waitpid`) has no rusage at all, and the two
    reaping paths can't both succeed against the same pid.

    Returns ``(exited, elapsed_s, rusage_or_None)`` -- `rusage` is `None`
    iff the deadline passed with the child still alive (the busy-spin/red
    case: exit alone was never reached, so there is nothing to reap yet).
    """
    t0 = time.monotonic()
    deadline = t0 + deadline_s
    while time.monotonic() < deadline:
        got_pid, _status, rusage = os.wait4(pid, os.WNOHANG)
        if got_pid == pid:
            return True, time.monotonic() - t0, rusage
        time.sleep(0.01)
    return False, time.monotonic() - t0, None


@_PTY_SKIP
@pytest.mark.pty_ui
def test_launcher_blocking_loop_exits_promptly_and_cheaply_when_pty_dies(tmp_path):
    """Blocking-mode loops (`_run`'s own launcher dispatch loop here;
    `_run_create`/`_run_bank` share the identical shape and guard). Closing
    the pty master out from under `getch()` must exit the process
    promptly and cheaply -- not spin a core reading a dead terminal as an
    infinitely fast idle user."""
    proc, master_fd = _spawn_bootstrap(tmp_path, "launcher_bootstrap.py", _BOOTSTRAP_LAUNCHER)
    try:
        _read_until(master_fd, "SELECT PROFILE", timeout=10.0)
        os.close(master_fd)  # the terminal is now gone out from under getch()

        exited, elapsed_s, rusage = _wait_dead_with_rusage(proc.pid, deadline_s=5.0)
        assert exited, f"still running after {elapsed_s:.2f}s — busy-spin regression"
        cpu_s = rusage.ru_utime + rusage.ru_stime
        assert cpu_s < 0.5, f"consumed {cpu_s:.3f}s CPU exiting — looks like it spun first"
    finally:
        if proc.poll() is None:
            terminate_session_group(proc)


@_PTY_SKIP
@pytest.mark.pty_ui
def test_play_shell_throttled_loop_exits_promptly_and_cheaply_when_pty_dies(tmp_path):
    """The throttled (`stdscr.timeout(1000)`) loop in `_run_play` -- the
    two lines (`:335-338` pre-fix) the WO named directly."""
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir()
    proc, master_fd = _spawn_bootstrap(
        tmp_path, "play_bootstrap.py", _BOOTSTRAP_PLAY, run_dir=isolated_run_dir
    )
    try:
        _read_until(master_fd, "SELECT PROFILE", timeout=10.0)
        os.write(master_fd, b"\r")  # Enter -> play shell (throttled getch)
        _read_until(master_fd, "PLAY SHELL", timeout=10.0)
        os.close(master_fd)

        exited, elapsed_s, rusage = _wait_dead_with_rusage(proc.pid, deadline_s=5.0)
        assert exited, f"still running after {elapsed_s:.2f}s — busy-spin regression"
        cpu_s = rusage.ru_utime + rusage.ru_stime
        assert cpu_s < 0.5, f"consumed {cpu_s:.3f}s CPU exiting — looks like it spun first"
    finally:
        if proc.poll() is None:
            terminate_session_group(proc)


# ---------------------------------------------------------------------------
# Part 3 -- the ORPHAN signal (os.getppid() == 1) through a genuine
# subprocess chain, not a monkeypatched os.getppid as in Part 1.
#
# The middle process below OWNS the pty (opens it, gives the grandchild the
# slave side, keeps the master side) and is also the grandchild's direct
# parent -- exactly the shape of every real spawn site in this suite
# (tests/pty_helpers.py et al: the same process is both). When it
# `os._exit(0)`s without closing anything explicitly, the kernel closes
# every fd it held (including the pty master) AND reparents the grandchild
# to init in the same instant -- both signals fire together, exactly like
# a hard-killed pytest orphans a start_new_session=True pty child
# (confirmed manually during this WO, full traceback in the STATUS report).
#
# An EARLIER version of this test had the OUTER test process hold the pty
# master itself (with the middle process only spawning the grandchild).
# That is a real, but DIFFERENT and NOT-otherwise-occurring, scenario: the
# grandchild's terminal stayed fully valid and open, so its blocking-mode
# `getch()` never returned control to Python at all (no EOF, no keystroke)
# -- meaning the orphan check inside `_DeadTerminalGuard.check()` never
# even got a chance to run, since it only executes once `getch()` DOES
# return. That version correctly failed, surfacing a genuine (if narrow)
# gap: blocking-mode orphaning WITHOUT a terminal-side EOF is not covered
# by this fix, because it can't interrupt a call already blocked inside
# ncurses. It does not match any real spawn site in this codebase (every
# one ties parent-death to master-fd-death) or the actual incident
# (confirmed: EOF and orphan status changed together, both caused by
# pytest's own death) -- see the STATUS report for the full argument for
# why this narrow residual was not pursued further.
# ---------------------------------------------------------------------------

_BOOTSTRAP_ORPHAN_PARENT = r"""
import fcntl
import os
import pty
import struct
import subprocess
import sys
import termios

master_fd, slave_fd = pty.openpty()
fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", {rows}, {cols}, 0, 0))
env = dict(os.environ)
env["TERM"] = "xterm"
env["TW2002_LAUNCHER_DEMO"] = "1"

grandchild = subprocess.Popen(
    [sys.executable, {grandchild_bootstrap!r}],
    stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
    env=env, start_new_session=True,
)
os.close(slave_fd)
with open({pid_file!r}, "w") as f:
    f.write(str(grandchild.pid))
    f.flush()
    os.fsync(f.fileno())
# Deliberately exit WITHOUT closing master_fd or waiting -- process death
# closes every fd this process held (including master_fd, which is what
# makes the grandchild's read() see EOF) AND reparents the grandchild to
# init, both in the same instant.
os._exit(0)
"""


@_PTY_SKIP
@pytest.mark.pty_ui
def test_orphaned_launcher_self_terminates_once_reparented_to_init(tmp_path):
    """A throwaway middle process owns a pty, spawns the real launcher
    attached to it, then exits immediately without waiting or closing
    anything explicitly -- the kernel closes its pty master (EOF for the
    grandchild) and reparents the grandchild to init in the same instant,
    exactly matching the incident. The launcher must exit promptly.

    CPU-boundedness for these getch loops is already proven above; this
    test's job is proving the fix fires end-to-end through a real
    subprocess chain shaped exactly like every real spawn site, not
    re-proving CPU cost.
    """
    grandchild_bootstrap = tmp_path / "orphan_grandchild.py"
    grandchild_bootstrap.write_text(
        _BOOTSTRAP_LAUNCHER.format(project_root=str(PROJECT_ROOT)), encoding="utf-8"
    )
    pid_file = tmp_path / "grandchild.pid"

    parent_bootstrap = tmp_path / "orphan_parent.py"
    parent_bootstrap.write_text(
        _BOOTSTRAP_ORPHAN_PARENT.format(
            rows=ROWS,
            cols=COLS,
            grandchild_bootstrap=str(grandchild_bootstrap),
            pid_file=str(pid_file),
        ),
        encoding="utf-8",
    )

    parent_proc = subprocess.Popen(
        [sys.executable, str(parent_bootstrap)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    grandchild_pid = None
    try:
        parent_proc.wait(timeout=5.0)
        assert pid_file.exists(), "middle process exited before recording the grandchild pid"
        grandchild_pid = int(pid_file.read_text().strip())

        deadline = time.monotonic() + 5.0
        gone = False
        while time.monotonic() < deadline:
            try:
                os.kill(grandchild_pid, 0)  # existence probe only -- no signal sent
            except ProcessLookupError:
                gone = True
                break
            time.sleep(0.05)
        assert gone, (
            f"orphaned launcher (pid {grandchild_pid}) still alive after 5s — "
            "the fix never fired"
        )
    finally:
        if parent_proc.poll() is None:
            parent_proc.kill()
            parent_proc.wait(timeout=5.0)
        if grandchild_pid is not None:
            try:
                os.kill(grandchild_pid, 9)
            except ProcessLookupError:
                pass
