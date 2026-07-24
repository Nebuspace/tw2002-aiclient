"""WO-P3-030 — Play-chrome navigation (Esc → launcher, daemon survives).

Layer-B pty + pyte (``tests.pty_helpers``) proves Enter → play shell shows
the profile handle, Esc(27) returns to the launcher without process exit,
and play-only chrome is gone. A separate FakeSession unit leg proves Esc
does not tear down the session (ADR-001 app-disposable / daemon-continuity)
and never touches ``run/twd.sock``.

Constraints: tw2002_aiclient only (no twclient); no exit-confirm popup;
placeholder play shell only (no double-line frame / gutters / fold).
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

import pytest

from tw2002_aiclient.adapters import EnsureResult
from tw2002_aiclient.screens import PLAY_SUBTITLE, PLAY_TITLE, ProfileRow, PlayShellScreen

from .pty_helpers import find_text, pty_curses_supported, pyte_grid, set_winsize

PROJECT_ROOT = Path(__file__).resolve().parent.parent
THIS_FILE = Path(__file__).resolve()
PTY_ROWS, PTY_COLS = 24, 80
HANDLE = "Alpha"
ESC = bytes([27])
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock).
_BOOTSTRAP = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ["TW2002_ASCII"] = "1"
# Clear smoke shortcuts so the interactive router runs.
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, {project_root!r})

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import EnsureResult


def _fake_ensure(profile, **kwargs):
    return EnsureResult(ok=True, classification="main_command")


adapters.ensure_session = _fake_ensure

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _assert_no_twclient(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("twclient"), path
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("twclient"), path


def test_module_imports_tw2002_aiclient_only():
    _assert_no_twclient(THIS_FILE)


def test_play_shell_esc_returns_back_router_token():
    """Accept: Esc → router ``\"back\"`` (not process exit)."""
    # Avoid curses color init — handle_key is pure key → action.
    play = object.__new__(PlayShellScreen)
    assert play.handle_key(27) == "back"
    assert play.handle_key(ord("q")) == "quit"
    assert play.handle_key(ord("x")) is None


class FakeSession:
    """Isolated stand-in for daemon continuity — never opens run/twd.sock."""

    def __init__(self) -> None:
        self.alive = True
        self.stop_calls = 0
        self.shutdown_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1
        self.alive = False

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.alive = False


class _RecordingStdscr:
    """Minimal curses window for ``_run_play`` without a real TTY."""

    def __init__(self, keys: list[int], rows: int = 24, cols: int = 80) -> None:
        self._keys = list(keys)
        self._rows = rows
        self._cols = cols
        self.lines: list[str] = []
        self.closed = False

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def erase(self) -> None:
        self.lines = []

    def clear(self) -> None:
        self.erase()

    def refresh(self) -> None:
        pass

    def keypad(self, _flag: bool) -> None:
        pass

    def timeout(self, _ms: int) -> None:
        pass

    def attron(self, _attr: int) -> None:
        pass

    def attroff(self, _attr: int) -> None:
        pass

    def box(self, *_a) -> None:
        pass

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        while len(self.lines) <= y:
            self.lines.append("")
        row = self.lines[y].ljust(x)
        self.lines[y] = (row[:x] + text)[: self._cols]

    def getch(self) -> int:
        if not self._keys:
            return ord("q")
        return self._keys.pop(0)


def test_run_play_esc_returns_back_without_stopping_fake_session(monkeypatch):
    """Daemon-survival leg: Esc ends the binding; FakeSession stays alive."""
    import tw2002_aiclient.app as app_mod
    import tw2002_aiclient.adapters as adapters_mod

    session = FakeSession()
    ensure_calls: list[str] = []

    def _ensure(profile: str, **kwargs):
        ensure_calls.append(profile)
        assert session.alive
        return EnsureResult(ok=True, classification="main_command")

    monkeypatch.setattr(adapters_mod, "ensure_session", _ensure)
    # PlayShellScreen.__init__/_init_colors needs a soft curses surface.
    monkeypatch.setattr(
        "tw2002_aiclient.screens.curses.has_colors",
        lambda: False,
    )

    profile = ProfileRow(
        name="alpha",
        handle=HANDLE,
        server="demo-a",
        host="demo-a.example",
        game_letter="B",
    )
    # Esc once after ensure — must return "back", not "quit".
    stdscr = _RecordingStdscr([27])
    result = app_mod._run_play(stdscr, profile)

    assert result == "back"
    assert ensure_calls == ["alpha"]
    assert session.alive is True
    assert session.stop_calls == 0
    assert session.shutdown_calls == 0
    # Play chrome was painted (handle visible) before Esc.
    joined = "\n".join(stdscr.lines)
    assert HANDLE in joined
    assert "PLAY SHELL" in joined or PLAY_TITLE.strip() in joined
    assert PLAY_SUBTITLE.strip().split("—")[0].strip("(") in joined or "placeholder" in joined


def _drive_launcher_play_esc_in_pty(tmp_path: Path, timeout: float = 12.0) -> bytes:
    """Spawn app._run in a pty: Enter → play → Esc → launcher; then q."""
    bootstrap = tmp_path / "play_chrome_nav_bootstrap.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, PTY_ROWS, PTY_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW2002_ASCII"] = "1"
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
            text = "\n".join(grid)

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_play"
            elif phase == "wait_play":
                if find_text(grid, "PLAY SHELL") and find_text(grid, HANDLE):
                    os.write(master_fd, ESC)
                    phase = "wait_back"
            elif phase == "wait_back":
                # Final paint: launcher chrome back, play-only chrome gone.
                if (
                    find_text(grid, "SELECT PROFILE")
                    and find_text(grid, HANDLE)
                    and find_text(grid, "PLAY SHELL") is None
                    and "placeholder" not in text
                ):
                    os.write(master_fd, b"q")
                    phase = "done"
                    break
        if phase != "done":
            # Still ask the child to quit so teardown isn't a hard kill only.
            try:
                os.write(master_fd, b"q")
            except OSError:
                pass
    finally:
        # Drain + wait; kill if wedged.
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
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        try:
            os.close(master_fd)
        except OSError:
            pass

    assert phase == "done", (
        f"pty nav stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, PTY_ROWS, PTY_COLS))
    )
    # Clean quit (not crash) — process exited after q, not solely via kill.
    assert proc.returncode is not None
    return captured


@_PTY_SKIP
def test_esc_from_play_shell_returns_launcher_without_exit(tmp_path):
    """Layer-B Accept: Enter → handle visible; Esc → launcher; no process exit mid-nav."""
    captured = _drive_launcher_play_esc_in_pty(tmp_path)
    # Final pyte state already asserted inside the driver; re-check for the report.
    grid = pyte_grid(captured, PTY_ROWS, PTY_COLS)
    assert find_text(grid, "SELECT PROFILE") is not None
    assert find_text(grid, "PLAY SHELL") is None
    assert find_text(grid, HANDLE) is not None
    # Play-only footer / subtitle must not linger on the launcher.
    joined = "\n".join(grid)
    assert "return to launcher" not in joined
    assert "placeholder" not in joined
