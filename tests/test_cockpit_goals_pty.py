"""WO-P3-034 wire — GOALS panel + 1 Hz status_provider refresh, Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
GOALS box the app.py wiring produces: a titled panel above FOCUS in
the left gutter, rendering nine honest-unknown lines with no provider
attached, and a known label/value once a stubbed daemon ``status`` response
is wired in. Layer-A coverage for the composer itself
(``compose_goals_lines``) lives in ``tests/test_cockpit_goals.py``; this
file only proves the ``PlayShellScreen``/``app.py`` wiring around it.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process (same convention as ``tests/test_cockpit_frame_pty.py``), and
``TW_RUN_DIR`` is always pointed at an isolated per-test tmp directory --
the app's real ``status_provider`` (``app._daemon_status_provider``) is
free to run unstubbed against that empty dir (its own ``send_request``
early-returns ``daemon_not_running`` without ever opening a socket), so the
no-provider-data scenario never depends on ambient repo state and never
touches ``run/twd.sock`` either way. The known-label scenario additionally
monkeypatches ``tw2002_aiclient.session.cli.send_request`` inside the
bootstrap -- mirroring how the frame-chrome pty suite stubs
``adapters.ensure_session`` -- rather than teaching production ``app.py``
about a test-only env var.

Mack-fix regression coverage (this file, bottom section): a bounded
``send_request`` poll timeout (HIGH -- a wedged daemon socket must not
freeze the play loop, Esc included, for 15s/tick) and a guarded
``compose_goals_lines`` call (defense-in-depth -- a raising composer must
not take the whole cockpit down).
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

pytestmark = pytest.mark.pty_ui


from tw2002_aiclient.cockpit.layout import frame_layout

from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as tests/test_cockpit_frame_pty.py's _BOOTSTRAP. Two opt-in GOALS
# status fixtures stub session_cli.send_request's "status" verb:
#   TW2002_TEST_GOALS_CREDITS=<int> -- a deterministic finite value.
#   TW2002_TEST_GOALS_INF=1         -- Mack's exact repro (credits=inf),
#                                      proving the compose-call guard holds
#                                      end to end even if the composer's own
#                                      _safe_int fix is ever regressed.
_BOOTSTRAP = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, {project_root!r})

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import EnsureResult


def _fake_ensure(profile, **kwargs):
    return EnsureResult(ok=True, classification="main_command")


adapters.ensure_session = _fake_ensure

_FIXTURE_CREDITS = os.environ.get("TW2002_TEST_GOALS_CREDITS")
_FIXTURE_INF = os.environ.get("TW2002_TEST_GOALS_INF") == "1"
if _FIXTURE_CREDITS is not None or _FIXTURE_INF:
    from tw2002_aiclient.session import cli as session_cli

    def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        if verb == "status":
            credits_value = float("inf") if _FIXTURE_INF else int(_FIXTURE_CREDITS)
            return {{"ok": True, "credits": credits_value, "turns_left": 7}}
        return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""

ROWS, COLS = 40, 160  # "full" tier -- both gutters present


def _drive_goals_pty(
    tmp_path: Path,
    rows: int,
    cols: int,
    *,
    fixture_credits: int | None = None,
    fixture_inf: bool = False,
    via_esc: bool = False,
    timeout: float = 12.0,
) -> bytes:
    """Spawn ``app._run`` in a pty sized ``rows``x``cols``: Enter from the
    launcher once its chrome is up, capture the play-shell cockpit frame
    once GOALS is visible (letting at least one ~1 Hz refresh tick land),
    then either quit directly (``via_esc=False``) or -- Mack's Esc-still-
    exits proof -- send Esc and wait for the launcher to reappear before
    quitting (``via_esc=True``). Mirrors
    ``tests/test_cockpit_frame_pty.py::_drive_cockpit_frame_pty``'s
    poll-and-decide loop.

    ``TW_RUN_DIR`` always points at an isolated tmp dir under ``tmp_path``
    -- distinct from wherever the bootstrap script itself lives -- so the
    real (unstubbed) status_provider path can never reach the project's own
    ``run/twd.sock`` regardless of which fixture (if any) is active.
    """
    bootstrap = tmp_path / f"goals_pty_bootstrap_{rows}x{cols}_{fixture_credits}_{fixture_inf}.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if fixture_credits is not None:
        env["TW2002_TEST_GOALS_CREDITS"] = str(fixture_credits)
    else:
        env.pop("TW2002_TEST_GOALS_CREDITS", None)
    if fixture_inf:
        env["TW2002_TEST_GOALS_INF"] = "1"
    else:
        env.pop("TW2002_TEST_GOALS_INF", None)
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

            grid = pyte_grid(captured, rows, cols)

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_frame"
            elif phase == "wait_frame":
                if find_text(grid, "GOALS"):
                    # Let at least one ~1 Hz refresh tick land before acting
                    # (proves the timeout-driven redraw doesn't crash/stall,
                    # including against a wedged-provider/raising-composer
                    # fixture).
                    time.sleep(1.3)
                    ready, _, _ = select.select([master_fd], [], [], 0.2)
                    if master_fd in ready:
                        try:
                            chunk = os.read(master_fd, 65536)
                            captured += chunk
                        except OSError:
                            pass
                    if via_esc:
                        os.write(master_fd, bytes([27]))  # Esc
                        phase = "wait_back"
                    else:
                        os.write(master_fd, b"q")
                        phase = "done"
                        break
            elif phase == "wait_back":
                if (
                    find_text(grid, "SELECT PROFILE")
                    and find_text(grid, HANDLE)
                    and find_text(grid, "PLAY SHELL") is None
                ):
                    os.write(master_fd, b"q")
                    phase = "done"
                    break
        if phase != "done":
            try:
                os.write(master_fd, b"q")
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
        f"pty GOALS drive stalled in phase={phase!r} at {rows}x{cols}; last grid:\n"
        + "\n".join(pyte_grid(captured, rows, cols))
    )
    return captured


@pytest.fixture(scope="module")
def _no_provider_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("goals_no_provider")
    return _drive_goals_pty(tmp_path, ROWS, COLS)


@pytest.fixture(scope="module")
def _fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("goals_fixture")
    return _drive_goals_pty(tmp_path, ROWS, COLS, fixture_credits=54321)


@_PTY_SKIP
def test_goals_title_visible_above_focus(_no_provider_capture):
    regions = frame_layout(ROWS, COLS)
    goals, focus = regions["goals"], regions["left_gutter"]
    assert goals is not None and focus is not None
    grid = pyte_grid(_no_provider_capture, ROWS, COLS)

    assert "GOALS" in grid[goals["y"]]
    assert "FOCUS" in grid[focus["y"]]
    # GOALS sits strictly above FOCUS, matching the layout split.
    assert goals["y"] < focus["y"]


@_PTY_SKIP
def test_no_provider_run_shows_all_unknown_honest_lines(_no_provider_capture):
    """No status_provider data (real transport, empty isolated run dir):
    every one of the 9 GOALS rows renders the unknown glyph -- honest, never
    blank, never invented."""
    regions = frame_layout(ROWS, COLS)
    goals = regions["goals"]
    grid = pyte_grid(_no_provider_capture, ROWS, COLS)

    content_top = goals["y"] + 1
    content_h = goals["h"] - 2
    content_left = goals["x"] + 1
    content_right = goals["x"] + goals["w"] - 1  # exclusive -- box's own right border
    assert content_h >= 1
    for row in grid[content_top : content_top + content_h]:
        cell = row[content_left:content_right].strip()
        assert cell, f"GOALS content row unexpectedly blank: {row!r}"
        assert cell.startswith("?"), f"expected unknown-glyph row, got cell={cell!r} full row={row!r}"


@_PTY_SKIP
def test_stubbed_provider_shows_known_credits_label_and_value(_fixture_capture):
    regions = frame_layout(ROWS, COLS)
    goals, focus = regions["goals"], regions["left_gutter"]
    grid = pyte_grid(_fixture_capture, ROWS, COLS)
    text = "\n".join(grid)

    assert "GOALS" in grid[goals["y"]]
    assert "Credits" in text
    assert "54,321" in text
    # FOCUS still present below GOALS -- the stub only touched GOALS's
    # data source, not the panel split itself.
    assert focus is not None
    assert "FOCUS" in grid[focus["y"]]


# ---------------------------------------------------------------------------
# Mack fix-round regression coverage.
# ---------------------------------------------------------------------------


def test_daemon_status_provider_uses_a_bounded_poll_timeout(monkeypatch):
    """HIGH: the GOALS poll must pass an explicit short timeout, never
    inherit ``send_request``'s much longer 15.0s transport default -- a
    bound-but-not-accepting daemon socket would otherwise wedge the whole
    play loop (Esc included) for that long, once per ~1 Hz tick."""
    import tw2002_aiclient.app as app_mod
    from tw2002_aiclient.session import cli as session_cli

    calls: list[dict] = []

    def _spy_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        calls.append({"verb": verb, "timeout": timeout, "run_dir": run_dir})
        return {"ok": True, "credits": 1}

    monkeypatch.setattr(session_cli, "send_request", _spy_send_request)

    provider = app_mod._daemon_status_provider(Path("/tmp/does-not-matter"))
    result = provider()

    assert result == {"ok": True, "credits": 1}
    assert len(calls) == 1
    assert calls[0]["verb"] == "status"
    assert calls[0]["timeout"] is not None
    assert calls[0]["timeout"] <= 2.0, f"poll timeout too long: {calls[0]['timeout']!r}"


class _RecordingWin:
    """Minimal fake curses window recording ``addstr`` writes into a 2D
    grid -- same shape as ``tests/test_cockpit_frame_pty.py::_GridWin``,
    kept local rather than imported to avoid cross-test-file coupling."""

    def __init__(self, rows: int, cols: int) -> None:
        self.rows, self.cols = rows, cols
        self.grid = [[" "] * cols for _ in range(rows)]

    def getmaxyx(self) -> tuple[int, int]:
        return self.rows, self.cols

    def erase(self) -> None:
        self.grid = [[" "] * self.cols for _ in range(self.rows)]

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        if not (0 <= y < self.rows):
            return
        for i, ch in enumerate(text):
            col = x + i
            if 0 <= col < self.cols:
                self.grid[y][col] = ch

    def refresh(self) -> None:
        return None

    def row_text(self, y: int) -> str:
        return "".join(self.grid[y])


def test_draw_survives_a_raising_compose_goals_lines(monkeypatch):
    """Defense-in-depth: ``draw()`` already guarded the ``status_provider()``
    call but not ``compose_goals_lines(...)`` itself -- Mack's repro
    (``credits=float('inf')`` reaching an unguarded ``int()``) killed the
    whole app through this gap. A raising composer must degrade to the
    panel's own honest fallback, never take the cockpit down, and never
    affect unrelated behavior like Esc handling."""
    from tw2002_aiclient import screens as screens_mod

    def _raise(*_a, **_k):
        raise OverflowError("cannot convert float infinity to integer")

    monkeypatch.setattr(screens_mod.cockpit_goals, "compose_goals_lines", _raise)
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(ROWS, COLS)
    screen = screens_mod.PlayShellScreen(win, profile)
    screen.status_provider = lambda: {"credits": float("inf")}

    screen.draw()  # must not raise

    regions = frame_layout(ROWS, COLS)
    goals = regions["goals"]
    assert "—" in win.row_text(goals["y"] + 1)
    # Esc handling is independent of draw() and still works after the crash.
    assert screen.handle_key(27) == "back"


@pytest.fixture(scope="module")
def _inf_credits_esc_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("goals_inf_esc")
    return _drive_goals_pty(tmp_path, ROWS, COLS, fixture_inf=True, via_esc=True)


@_PTY_SKIP
def test_inf_credits_status_survives_and_esc_still_exits(_inf_credits_esc_capture):
    """Mack's exact end-to-end repro, paired proof: a stubbed status of
    ``{"ok": True, "credits": float("inf"), "turns_left": 7}`` must not
    freeze or crash the app, and Esc must still return to the launcher
    afterward -- proving the play loop stayed alive and responsive through
    at least one bad-data refresh tick. Passes with either fix alone
    (monk-goals's composer-side guard or this file's compose-call wrap);
    the pairing is what the driver actually exercises end to end."""
    grid = pyte_grid(_inf_credits_esc_capture, ROWS, COLS)
    assert find_text(grid, "SELECT PROFILE") is not None
    assert find_text(grid, "PLAY SHELL") is None
    assert find_text(grid, HANDLE) is not None
