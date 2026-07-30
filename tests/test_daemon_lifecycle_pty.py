"""WO-CLIENT-DAEMON-OWNERSHIP — PTY proofs for ONLINE + quit confirm.

Layer-B: real curses in a pty. Esc→launcher zero-stop traffic stays in
``test_play_esc_daemon_survival``; this file proves ONLINE paint and the
whole-app quit confirm (default-No / Yes / stop-failure stay).
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

from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PTY_ROWS, PTY_COLS = 24, 100

pytestmark = pytest.mark.pty_ui

_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

_BOOTSTRAP = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ["TW2002_ASCII"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, {project_root!r})

from tw2002_aiclient import daemon_lifecycle as life

_marker = {marker!r}
_mode = os.environ.get("TW2002_QUIT_STOP_MODE", "ok")


def _presence(**kwargs):
    return life.Presence(kind=life.PRESENCE_ONLINE, profile="alpha")


def _should(**kwargs):
    return True


def _stop(**kwargs):
    if _marker:
        open(_marker, "w", encoding="utf-8").write(_mode)
    if _mode == "fail":
        return life.StopResult(ok=False, reason="busy", detail="held")
    return life.StopResult(ok=True)


life.read_presence = _presence
life.should_confirm_quit_stop = _should
life.stop_daemon = _stop

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _drive(tmp_path: Path, keys_after_confirm: bytes, *, stop_mode: str = "ok",
           timeout: float = 12.0) -> tuple[bytes, Path]:
    marker = tmp_path / "stop_marker"
    bootstrap = tmp_path / "lifecycle_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP.format(project_root=str(PROJECT_ROOT), marker=str(marker)),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, PTY_ROWS, PTY_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW2002_ASCII"] = "1"
    env["TW_RUN_DIR"] = str(run_dir)
    env["TW2002_QUIT_STOP_MODE"] = stop_mode
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

    captured = b""
    phase = "wait_launcher"
    deadline = time.monotonic() + timeout
    try:
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

            grid = pyte_grid(captured, PTY_ROWS, PTY_COLS)
            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, "ONLINE"):
                    os.write(master_fd, b"q")
                    phase = "wait_confirm"
            elif phase == "wait_confirm":
                if find_text(grid, "Stop daemon and disconnect"):
                    os.write(master_fd, keys_after_confirm)
                    phase = "done"
                    break
        if phase != "done":
            try:
                os.write(master_fd, b"q\n")
            except OSError:
                pass
    finally:
        drain_deadline = time.monotonic() + 5.0
        while time.monotonic() < drain_deadline and proc.poll() is None:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
        terminate_session_group(proc)
        try:
            os.close(master_fd)
        except OSError:
            pass

    assert phase == "done", (
        f"pty stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, PTY_ROWS, PTY_COLS))
    )
    return captured, marker


@_PTY_SKIP
def test_launcher_shows_online_and_quit_confirm_default_no(tmp_path):
    captured, marker = _drive(tmp_path, b"\n")
    grid = pyte_grid(captured, PTY_ROWS, PTY_COLS)
    assert find_text(grid, "ONLINE") is not None
    assert find_text(grid, "Stop daemon and disconnect alpha") is not None
    assert not marker.exists(), "default No must not call stop"


@_PTY_SKIP
def test_quit_yes_issues_stop(tmp_path):
    captured, marker = _drive(tmp_path, b"y")
    assert marker.exists()
    assert marker.read_text(encoding="utf-8") == "ok"
    grid = pyte_grid(captured, PTY_ROWS, PTY_COLS)
    assert find_text(grid, "Stop daemon and disconnect") is not None


@_PTY_SKIP
def test_quit_stop_failure_stays_in_app(tmp_path):
    # Drive confirm → y (fail) → then wait for the failure note before killing.
    marker = tmp_path / "stop_marker"
    bootstrap = tmp_path / "lifecycle_bootstrap.py"
    bootstrap.write_text(
        _BOOTSTRAP.format(project_root=str(PROJECT_ROOT), marker=str(marker)),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, PTY_ROWS, PTY_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW2002_ASCII"] = "1"
    env["TW_RUN_DIR"] = str(run_dir)
    env["TW2002_QUIT_STOP_MODE"] = "fail"
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

    captured = b""
    phase = "wait_launcher"
    deadline = time.monotonic() + 12.0
    try:
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

            grid = pyte_grid(captured, PTY_ROWS, PTY_COLS)
            if phase == "wait_launcher":
                if find_text(grid, "ONLINE"):
                    os.write(master_fd, b"q")
                    phase = "wait_confirm"
            elif phase == "wait_confirm":
                if find_text(grid, "Stop daemon and disconnect"):
                    os.write(master_fd, b"y")
                    phase = "wait_fail"
            elif phase == "wait_fail":
                if find_text(grid, "stop failed"):
                    phase = "done"
                    break
    finally:
        terminate_session_group(proc)
        try:
            os.close(master_fd)
        except OSError:
            pass

    assert phase == "done", (
        f"pty stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, PTY_ROWS, PTY_COLS))
    )
    assert marker.exists()
    assert find_text(pyte_grid(captured, PTY_ROWS, PTY_COLS), "stop failed") is not None
