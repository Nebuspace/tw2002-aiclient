"""WO-P3-040 wire — semantic chrome tones, Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
cockpit chrome ``screens.py``/``app.py`` produce once wired to
``cockpit.tones`` (WO-P3-040, single source of truth for the 7-tone
palette): every box border/title still renders the ``"info"`` chrome tone
(cyan, non-bold) except the outer frame's own bold exception (already
proven at ``tests/test_cockpit_frame_pty.py``, not re-proven exhaustively
here), and the GAME viewport's own border/title flips to the ``"danger"``
tone rendered NON-bold (canon `visual-language.md` "the viewport border is
a STATE surface") the instant the shared ``status`` snapshot carries a
real, definite ``connected: False``. A status that lacks that field (or no
status at all) leaves the border at its default chrome cyan — the
honest-unknown rule (``PlayShellScreen._viewport_border_attr``'s own
docstring): never claim danger without real data.

Cell-attribute proofs read pyte's raw ``screen.buffer[row][col].fg`` /
``.bold`` directly, never an ANSI-escape regex (house convention, see
``tests/test_cockpit_frame_pty.py``'s own module docstring). Capture is
condition-driven on real fixture CONTENT (a distinguishing GOALS credits
value, or the honest-empty ``"Exploring…"`` DECISIONS marker) — never the
bare "GAME"/"PLAY SHELL" box title, which paints on the first frame
regardless of whether the stubbed status has reached the composers yet
(the WO-P3-039/038 lesson, mirrored from ``tests/test_cockpit_fold_pty.py``
/ ``tests/test_cockpit_liveness_pty.py``).

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process (same convention as every sibling cockpit-panel pty suite), and
``TW_RUN_DIR`` always points at an isolated per-test tmp directory — the
real ``status_provider`` (``app._daemon_status_provider``) is free to run
unstubbed against that empty dir (its own ``send_request`` early-returns
``daemon_not_running`` without ever opening a socket) for the no-fixture
scenario, and the ``connected``/``disconnected``/``no_connected_field``
fixtures additionally monkeypatch ``tw2002_aiclient.session.cli.
send_request`` inside the bootstrap — never ``run/twd.sock`` either way.

**REVISE (Mack CRITICAL, pair-collision regression):** ``curses`` color-pair
NUMBERS are global to the whole terminal session, not scoped per class/
screen instance. Before ``_SharedPairs`` (``tw2002_aiclient/screens.py``),
every screen in that module hardcoded its own pair 1/2 with DIFFERENT
colors, so constructing a SECOND screen mid-session silently repainted
whatever pair number(s) it reused — corrupting a PREVIOUSLY constructed
screen's already-cached attr ints (a curses attr int only encodes the pair
NUMBER; the terminal resolves it to an actual color at render time, not at
attr-computation time). Reproduced (Mack's PoC): a launcher -> play -> Esc
-> back round trip permanently repainted the SAME ``LauncherScreen``
instance's warn row red and its ok row cyan for the rest of the process.
``test_launcher_row_colors_survive_a_play_shell_round_trip`` below pins the
fix: one continuously-captured process takes a color snapshot of the
launcher's warn/ok rows BEFORE entering the play shell, navigates
launcher -> play -> Esc -> back to the SAME launcher instance, and asserts
the SAME rows still carry identical fg/bold — the exact scenario Mack's PoC
reproduced.
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

import curses

from tw2002_aiclient.cockpit.layout import frame_layout

from .pty_helpers import find_text, pty_curses_supported, pyte_grid, pyte_screen, set_winsize

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# Full tier — every gutter present, matches tests/test_cockpit_frame_pty.py's
# own FULL constants so GOALS/DECISIONS/GAME are all simultaneously visible.
FULL_ROWS, FULL_COLS = 40, 160
_DOUBLE_GLYPHS_UNICODE = ("╔", "╗", "╚", "╝")
_THIN_GLYPHS_UNICODE = ("╭", "╮", "╰", "╯")

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as every sibling cockpit-panel pty suite's own bootstrap. Each
# fixture stubs session_cli.send_request's "status" verb with a distinct
# credits value (the pty drive's own content-marker) plus the connected/
# idle_ms shape the real wire actually carries
# (tw2002_aiclient/session/protocol.py's "status" dispatch:
# resp["connected"] = session.conn.connected, resp["idle_ms"] = int(...)).
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

_TONE_FIXTURE = os.environ.get("TW2002_TEST_TONE_FIXTURE", "")
# Gap 1 (WO-P4-054): a status-PHASE FILE the outer test process rewrites
# mid-flight, mirroring tests/test_cockpit_liveness_pty.py's own
# controlled-clock-file idiom -- lets a single continuously-driven process
# walk a real connected -> disconnected -> connected cycle instead of only
# ever proving one-way fixtures. Opt-in (empty unless a reconnect-cycle
# driver sets it), so every existing static _TONE_FIXTURE scenario above is
# untouched.
_TONE_STATUS_FILE = os.environ.get("TW2002_TEST_TONE_STATUS_FILE", "")
_RECONNECT_PHASES = {{
    "recon_a": {{"ok": True, "connected": True, "idle_ms": 1000, "credits": 555666, "turns_left": 40}},
    "recon_b": {{"ok": True, "connected": False, "idle_ms": 999999, "credits": 666777, "turns_left": 50}},
    "recon_c": {{"ok": True, "connected": True, "idle_ms": 1000, "credits": 777888, "turns_left": 60}},
}}
if _TONE_FIXTURE or _TONE_STATUS_FILE:
    from pathlib import Path as _Path

    from tw2002_aiclient.session import cli as session_cli

    def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        if verb != "status":
            return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}
        if _TONE_STATUS_FILE:
            try:
                phase = _Path(_TONE_STATUS_FILE).read_text().strip()
            except OSError:
                phase = ""
            fixture = _RECONNECT_PHASES.get(phase)
            if fixture is not None:
                return dict(fixture)
            return {{"ok": False, "error": "unknown_reconnect_phase"}}
        if _TONE_FIXTURE == "connected":
            # Fresh (idle_ms well under the 5.0s STALE_RX_THRESHOLD_S) ->
            # status_semantic("ok") -> the viewport border stays default
            # chrome cyan, unchanged.
            return {{
                "ok": True,
                "connected": True,
                "idle_ms": 1000,
                "credits": 111222,
                "turns_left": 10,
            }}
        if _TONE_FIXTURE == "disconnected":
            return {{
                "ok": True,
                "connected": False,
                "idle_ms": 999999,
                "credits": 222333,
                "turns_left": 20,
            }}
        if _TONE_FIXTURE == "no_connected_field":
            # A real, "ok" daemon response that simply omits "connected" --
            # the honest-unknown gate, not the "no daemon at all" gate.
            return {{
                "ok": True,
                "credits": 333444,
                "turns_left": 30,
            }}
        return {{"ok": False, "error": "unknown_test_fixture"}}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining ``master_fd`` for ``seconds`` of wall time, accumulating
    onto ``captured`` -- a single post-condition ``read()`` isn't reliable
    (``PlayShellScreen.draw()``'s one ``refresh()`` call still spans
    multiple OS-level pty read chunks for a full frame), same helper shape
    as ``tests/test_cockpit_fold_pty.py``/``tests/test_cockpit_liveness_pty.py``'s
    own ``_settle``.
    """
    deadline = time.monotonic() + seconds
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
    return captured


def _drive_tone_pty(
    tmp_path: Path,
    *,
    ready_text: str,
    fixture: str = "",
    ascii_mode: bool = False,
    rows: int = FULL_ROWS,
    cols: int = FULL_COLS,
    timeout: float = 12.0,
) -> bytes:
    """Spawn ``app._run`` in a pty sized ``rows``x``cols``: Enter from the
    launcher once its chrome is up, capture the play-shell cockpit frame
    once ``ready_text`` is visible ANYWHERE on screen (letting at least one
    ~1 Hz refresh tick fully settle after that), then quit.

    ``ready_text`` must be the actual fixture-specific CONTENT this drive is
    looking for (a distinguishing GOALS credits value, or the honest-empty
    ``"Exploring…"`` marker for the no-fixture case) -- never the bare
    ``"GAME"``/``"PLAY SHELL"`` box title, which is drawn on the FIRST frame
    regardless of whether the status_provider's data has reached the
    composers yet (the WO-P3-038/039 lesson, mirrored verbatim from
    ``tests/test_cockpit_fold_pty.py``'s own ``_drive_fold_pty``).

    ``TW_RUN_DIR`` always points at an isolated tmp dir under ``tmp_path``
    so the real (unstubbed) status_provider path can never reach the
    project's own ``run/twd.sock`` regardless of which fixture is active.
    """
    bootstrap = tmp_path / f"tone_pty_bootstrap_{rows}x{cols}_{fixture or 'none'}_{int(ascii_mode)}.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if ascii_mode:
        env["TW2002_ASCII"] = "1"
    else:
        env.pop("TW2002_ASCII", None)
    if fixture:
        env["TW2002_TEST_TONE_FIXTURE"] = fixture
    else:
        env.pop("TW2002_TEST_TONE_FIXTURE", None)
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
                if find_text(grid, ready_text):
                    captured = _settle(master_fd, captured, 1.6)
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
        f"pty tone drive stalled in phase={phase!r} at {rows}x{cols} fixture={fixture!r}; "
        "last grid:\n" + "\n".join(pyte_grid(captured, rows, cols))
    )
    return captured


@pytest.fixture(scope="module")
def _connected_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tone_connected")
    return _drive_tone_pty(tmp_path, ready_text="111,222", fixture="connected")


@pytest.fixture(scope="module")
def _disconnected_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tone_disconnected")
    return _drive_tone_pty(tmp_path, ready_text="222,333", fixture="disconnected")


@pytest.fixture(scope="module")
def _no_connected_field_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tone_no_connected_field")
    return _drive_tone_pty(tmp_path, ready_text="333,444", fixture="no_connected_field")


@pytest.fixture(scope="module")
def _no_daemon_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tone_no_daemon")
    # No fixture -> status_provider resolves to None (daemon_not_running,
    # never touching run/twd.sock) -> DECISIONS' own honest-empty collapse,
    # ["—", "Exploring…"] -- wait for its own second line, genuine content.
    return _drive_tone_pty(tmp_path, ready_text="Exploring…")


@pytest.fixture(scope="module")
def _ascii_disconnected_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tone_ascii_disconnected")
    return _drive_tone_pty(tmp_path, ready_text="222,333", fixture="disconnected", ascii_mode=True)


# ---------------------------------------------------------------------------
# (a) Chrome-tone proof at the full tier: every non-outer box border stays
# the "info" tone (cyan, non-bold); the outer frame keeps its own bold
# exception. Sourced dynamically off cockpit.tones.SEMANTIC_COLORS rather
# than a hardcoded "cyan" literal, proving the WIRING reads the single
# source of truth (tests/test_cockpit_frame_pty.py already pins the literal
# "cyan"/bold outer-frame behavior; this test complements it with the
# tones-sourced GAME viewport border specifically, since that box is new
# ground for this WO -- its default/connected-ok rendering).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_full_tier_viewport_border_default_chrome_tone_matches_tones_table(_connected_capture):
    from tw2002_aiclient.cockpit import tones as cockpit_tones

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert center["border"] is True
    screen = pyte_screen(_connected_capture, FULL_ROWS, FULL_COLS)

    info_fg_name, _info_bold = cockpit_tones.SEMANTIC_COLORS["info"]
    border_cell = screen.buffer[center["y"]][center["x"]]
    assert border_cell.data == "╔"
    assert border_cell.fg == info_fg_name, (
        f"expected the GAME viewport border to render the tones-table 'info' fg "
        f"({info_fg_name!r}) when connected+fresh, got {border_cell.fg!r}"
    )
    assert not border_cell.bold, "the viewport border's default chrome is non-bold (only the outer frame is bold)"

    # Outer frame's own bold exception, unchanged.
    outer = regions["outer"]
    outer_cell = screen.buffer[outer["y"]][outer["x"]]
    assert outer_cell.fg == info_fg_name
    assert outer_cell.bold


# ---------------------------------------------------------------------------
# (b) Disconnected fixture: viewport border cell fg red, non-bold.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_disconnected_status_flips_viewport_border_to_danger_non_bold(_disconnected_capture):
    from tw2002_aiclient.cockpit import tones as cockpit_tones

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    screen = pyte_screen(_disconnected_capture, FULL_ROWS, FULL_COLS)

    danger_fg_name, _danger_bold = cockpit_tones.SEMANTIC_COLORS["danger"]
    assert danger_fg_name == "red"

    border_cell = screen.buffer[center["y"]][center["x"]]
    assert border_cell.data == "╔", "viewport border glyph must stay the double-line corner, only color/attr changes"
    assert border_cell.fg == danger_fg_name, (
        f"expected the disconnected viewport border to flip to {danger_fg_name!r}, got {border_cell.fg!r}"
    )
    assert not border_cell.bold, (
        "canon (visual-language.md 'the viewport border is a STATE surface') calls for "
        "red NON-bold -- the tone table's own (red, bold=True) 'danger' attr must NOT be used here"
    )

    # The title row (same border) still carries "GAME" -- only the tone
    # changed, never the text.
    grid = pyte_grid(_disconnected_capture, FULL_ROWS, FULL_COLS)
    assert "GAME" in grid[center["y"]]

    # Sibling panels stay unaffected -- only the viewport border is a STATE
    # surface; GOALS/outer chrome keep their own default cyan.
    outer = regions["outer"]
    outer_cell = screen.buffer[outer["y"]][outer["x"]]
    assert outer_cell.fg == "cyan"
    goals = regions["goals"]
    assert goals is not None
    goals_border_cell = screen.buffer[goals["y"]][goals["x"]]
    assert goals_border_cell.fg == "cyan"


# ---------------------------------------------------------------------------
# (c) Honest-unknown: a real "ok" status that simply lacks "connected" must
# never be treated as disconnected -- the border stays default chrome cyan.
# A second leg proves the same for "no daemon at all" (status_provider
# resolves to None entirely).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_status_missing_connected_field_leaves_viewport_border_chrome_cyan(
    _no_connected_field_capture,
):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    screen = pyte_screen(_no_connected_field_capture, FULL_ROWS, FULL_COLS)

    border_cell = screen.buffer[center["y"]][center["x"]]
    assert border_cell.fg == "cyan", (
        "a real daemon status that omits 'connected' must never be treated as "
        f"disconnected -- honest-unknown must leave the border cyan, got fg={border_cell.fg!r}"
    )
    assert not border_cell.bold


@_PTY_SKIP
def test_no_daemon_at_all_leaves_viewport_border_chrome_cyan(_no_daemon_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    screen = pyte_screen(_no_daemon_capture, FULL_ROWS, FULL_COLS)

    border_cell = screen.buffer[center["y"]][center["x"]]
    assert border_cell.fg == "cyan", (
        f"no status_provider data at all must never claim danger -- got fg={border_cell.fg!r}"
    )
    assert not border_cell.bold


# ---------------------------------------------------------------------------
# (d) ASCII parity: TW2002_ASCII=1 loses zero information -- the SAME
# disconnected status still flips the border to red/non-bold (color is
# additive, unaffected by the glyph-set switch), and the same distinguishing
# credits value renders as the same text (numbers are never glyph-swapped).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_ascii_mode_disconnected_flip_same_tone_as_unicode_mode(_ascii_disconnected_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    screen = pyte_screen(_ascii_disconnected_capture, FULL_ROWS, FULL_COLS)
    grid = list(screen.display)
    text = "\n".join(grid)

    border_cell = screen.buffer[center["y"]][center["x"]]
    assert border_cell.data == "+", "ASCII twin corner glyph expected"
    assert border_cell.fg == "red"
    assert not border_cell.bold

    # No unicode box-drawing glyph leaked through under the ASCII flag.
    for glyph in _DOUBLE_GLYPHS_UNICODE + _THIN_GLYPHS_UNICODE:
        assert glyph not in text

    # Information parity: the same distinguishing data value renders
    # identically regardless of glyph set (numbers are never ASCII-swapped).
    assert "222,333" in text
    assert "GAME" in grid[center["y"]]
    assert "PLAY SHELL" in text


# ---------------------------------------------------------------------------
# (d2) Gap 1 (WO-P4-054): reconnect transition through the real curses draw.
# A one-way disconnect fixture (like (b) above) cannot prove the border
# EVER returns to chrome -- if the attr were latched on the instance after
# the first danger, every one-way test would still pass and the border
# would never come back. This drives ONE continuously-running process
# through a real connected -> disconnected -> connected cycle via a
# status-PHASE FILE the outer process rewrites mid-flight (mirrors
# tests/test_cockpit_liveness_pty.py's own controlled-clock-file idiom),
# capturing a full-buffer snapshot at each phase only once that phase's own
# distinguishing credits value is actually visible on screen -- condition-
# driven via find_text, never a fixed sleep standing in for the transition
# itself (the settle window after each write only lets the real ~1 Hz
# redraw loop flush a frame that already carries the new phase's data, the
# same "let a tick land" wait every sibling pty suite already uses).
# ---------------------------------------------------------------------------


def _drive_reconnect_cycle_pty(tmp_path: Path, timeout: float = 16.0) -> tuple[bytes, bytes, bytes]:
    bootstrap = tmp_path / "tone_reconnect_cycle_bootstrap.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)
    status_file = tmp_path / "recon_phase.txt"
    status_file.write_text("recon_a", encoding="utf-8")

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, FULL_ROWS, FULL_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    env["TW2002_TEST_TONE_STATUS_FILE"] = str(status_file)
    env.pop("TW2002_ASCII", None)
    env.pop("TW2002_TEST_TONE_FIXTURE", None)
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
    capture_a: bytes | None = None
    capture_b: bytes | None = None
    capture_c: bytes | None = None
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

            grid = pyte_grid(captured, FULL_ROWS, FULL_COLS)

            if phase == "wait_launcher":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, HANDLE):
                    os.write(master_fd, b"\r")
                    phase = "wait_a"
            elif phase == "wait_a":
                if find_text(grid, "555,666"):
                    captured = _settle(master_fd, captured, 1.6)
                    capture_a = captured
                    status_file.write_text("recon_b", encoding="utf-8")
                    phase = "wait_b"
            elif phase == "wait_b":
                if find_text(grid, "666,777"):
                    captured = _settle(master_fd, captured, 1.6)
                    capture_b = captured
                    status_file.write_text("recon_c", encoding="utf-8")
                    phase = "wait_c"
            elif phase == "wait_c":
                if find_text(grid, "777,888"):
                    captured = _settle(master_fd, captured, 1.6)
                    capture_c = captured
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

    assert (
        phase == "done" and capture_a is not None and capture_b is not None and capture_c is not None
    ), (
        f"reconnect-cycle pty drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return capture_a, capture_b, capture_c


@pytest.fixture(scope="module")
def _reconnect_cycle_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tone_reconnect_cycle")
    return _drive_reconnect_cycle_pty(tmp_path)


@_PTY_SKIP
def test_pty_viewport_border_returns_to_identical_chrome_cell_after_reconnect(_reconnect_cycle_capture):
    """The border must return to the IDENTICAL rendered cyan cell after a
    real reconnect -- not merely 'also cyan' (which a latched-then-partial
    -reset bug could still satisfy), the same fg AND bold as the very first
    connected frame."""
    capture_a, capture_b, capture_c = _reconnect_cycle_capture
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]

    screen_a = pyte_screen(capture_a, FULL_ROWS, FULL_COLS)
    screen_b = pyte_screen(capture_b, FULL_ROWS, FULL_COLS)
    screen_c = pyte_screen(capture_c, FULL_ROWS, FULL_COLS)

    cell_a = screen_a.buffer[center["y"]][center["x"]]
    cell_b = screen_b.buffer[center["y"]][center["x"]]
    cell_c = screen_c.buffer[center["y"]][center["x"]]

    assert cell_a.fg == "cyan" and not cell_a.bold, f"phase A (connected) sanity: got fg={cell_a.fg!r} bold={cell_a.bold!r}"
    assert cell_b.fg == "red" and not cell_b.bold, (
        f"phase B (disconnected) must render the real danger flip: got fg={cell_b.fg!r} bold={cell_b.bold!r}"
    )
    assert cell_c.fg == cell_a.fg and cell_c.bold == cell_a.bold, (
        "phase C (reconnected) must return to the IDENTICAL chrome cell as phase A, "
        f"got fg={cell_c.fg!r} bold={cell_c.bold!r} vs initial fg={cell_a.fg!r} bold={cell_a.bold!r}"
    )

    # Each capture really is the phase it claims to be (distinguishing
    # content actually landed), not a stale replay of a prior phase.
    grid_a = pyte_grid(capture_a, FULL_ROWS, FULL_COLS)
    grid_b = pyte_grid(capture_b, FULL_ROWS, FULL_COLS)
    grid_c = pyte_grid(capture_c, FULL_ROWS, FULL_COLS)
    assert any("555,666" in row for row in grid_a)
    assert any("666,777" in row for row in grid_b)
    assert any("777,888" in row for row in grid_c)

    # "GAME" title text never moves outside the game cells for any phase.
    assert "GAME" in grid_a[center["y"]]
    assert "GAME" in grid_b[center["y"]]
    assert "GAME" in grid_c[center["y"]]


# ---------------------------------------------------------------------------
# (e) Esc -> back / q -> quit unchanged -- the tone wiring adds no new key
# handling. Mirrors tests/test_cockpit_fold_pty.py's own regression leg.
# ---------------------------------------------------------------------------


class _NullWin:
    def __init__(self, rows: int, cols: int) -> None:
        self._rows, self._cols = rows, cols

    def getmaxyx(self):
        return (self._rows, self._cols)

    def erase(self):
        return None

    def addstr(self, *a, **k):
        return None

    def refresh(self):
        return None


def test_play_shell_screen_handle_key_unchanged_esc_and_q_only(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(FULL_ROWS, FULL_COLS), profile)

    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("Q")) == "quit"
    for key in (curses.KEY_UP, curses.KEY_DOWN, ord("1"), ord("d"), ord(" ")):
        assert screen.handle_key(key) is None


# ---------------------------------------------------------------------------
# Poll-guard: the viewport border is a SIXTH consumer of the same shared
# status_provider() snapshot -- still exactly one poll per draw() at a tier
# where the border is present, mirroring
# tests/test_cockpit_fold_pty.py/tests/test_cockpit_liveness_pty.py's own
# poll-guard tests.
# ---------------------------------------------------------------------------


def test_poll_guard_fires_exactly_once_at_full_tier_with_viewport_border(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    assert regions["center"]["border"] is True

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _NullWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"connected": False, "idle_ms": 1, "credits": 1}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one status_provider poll with the viewport border consuming the "
        f"same snapshot, got {len(calls)}"
    )


# ---------------------------------------------------------------------------
# Pure logic unit tests: _viewport_border_attr / _resolve_last_rx_age_s
# hardening, no pty/curses needed.
# ---------------------------------------------------------------------------


def _make_screen(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    return screens_mod.PlayShellScreen(_NullWin(FULL_ROWS, FULL_COLS), profile)


def test_viewport_border_attr_non_dict_status_stays_chrome(monkeypatch):
    screen = _make_screen(monkeypatch)
    assert screen._viewport_border_attr(None) == screen._chrome_attr
    assert screen._viewport_border_attr("not a dict") == screen._chrome_attr
    assert screen._viewport_border_attr({}) == screen._chrome_attr


def test_viewport_border_attr_non_bool_connected_stays_chrome(monkeypatch):
    screen = _make_screen(monkeypatch)
    # A malformed wire payload -- "connected" present but not a real bool --
    # must never be treated as a definite disconnect signal.
    assert screen._viewport_border_attr({"connected": "false", "idle_ms": 1}) == screen._chrome_attr
    assert screen._viewport_border_attr({"connected": 0, "idle_ms": 1}) == screen._chrome_attr
    assert screen._viewport_border_attr({"connected": None, "idle_ms": 1}) == screen._chrome_attr


def test_viewport_border_attr_hostile_idle_ms_never_raises_and_stays_ok(monkeypatch):
    screen = _make_screen(monkeypatch)
    # connected=True with hostile idle_ms -> _resolve_last_rx_age_s degrades
    # to 0.0 (freshest-possible, never fabricated staleness) -> status_semantic
    # still resolves "ok" -> chrome, not a crash and not a false "warn".
    for idle_ms in (None, "garbage", float("inf"), float("nan"), -5, object()):
        attr = screen._viewport_border_attr({"connected": True, "idle_ms": idle_ms})
        assert attr == screen._chrome_attr, f"idle_ms={idle_ms!r} must degrade to chrome, not raise/escalate"


def test_viewport_border_attr_disconnected_returns_danger_attr(monkeypatch):
    screen = _make_screen(monkeypatch)
    assert screen._viewport_border_attr({"connected": False, "idle_ms": 0}) == screen._viewport_danger_attr


def test_viewport_border_attr_stale_but_connected_stays_chrome_not_danger(monkeypatch):
    """status_semantic's "warn" tone (connected but stale) must NOT flip the
    border -- canon describes a strict connected/disconnected flip only; no
    gauge/three-way surface is in scope for this WO."""
    screen = _make_screen(monkeypatch)
    attr = screen._viewport_border_attr({"connected": True, "idle_ms": 999_000})  # 999s, well past 5.0s
    assert attr == screen._chrome_attr


# ---------------------------------------------------------------------------
# Gap 1 (WO-P4-054): the reconnect direction, unit level. Every disconnect
# assertion above is a single fresh call on a fresh screen -- a set of
# one-way tests cannot prove the border ever returns to chrome. If the attr
# were ever latched/cached on the instance after the first danger, every
# test above would still pass and the border would never come back. These
# call _viewport_border_attr repeatedly on the SAME instance across a real
# cyan -> danger -> cyan cycle (and a longer oscillation), asserting the
# return is IDENTICAL to the very first chrome call, not merely "also
# chrome".
# ---------------------------------------------------------------------------


def test_viewport_border_attr_round_trips_cyan_danger_cyan_on_reconnect(monkeypatch):
    screen = _make_screen(monkeypatch)
    connected_status = {"connected": True, "idle_ms": 0}
    disconnected_status = {"connected": False, "idle_ms": 0}

    first_chrome = screen._viewport_border_attr(connected_status)
    assert first_chrome == screen._chrome_attr

    danger = screen._viewport_border_attr(disconnected_status)
    assert danger == screen._viewport_danger_attr
    assert danger != first_chrome

    second_chrome = screen._viewport_border_attr(connected_status)
    assert second_chrome == first_chrome, (
        "the border must return to the SAME chrome attr on reconnect, not stay latched on danger"
    )


def test_viewport_border_attr_survives_five_cycle_oscillation(monkeypatch):
    """A "flips once then latches" bug could still survive a single round
    trip if it only breaks on the SECOND transition onward -- oscillate
    five full cycles and assert every single call, not just the
    endpoints."""
    screen = _make_screen(monkeypatch)
    connected_status = {"connected": True, "idle_ms": 0}
    disconnected_status = {"connected": False, "idle_ms": 0}

    for cycle in range(5):
        attr = screen._viewport_border_attr(connected_status)
        assert attr == screen._chrome_attr, f"cycle {cycle}: expected chrome on connected"
        attr = screen._viewport_border_attr(disconnected_status)
        assert attr == screen._viewport_danger_attr, f"cycle {cycle}: expected danger on disconnected"


# ---------------------------------------------------------------------------
# Gap 2 (WO-P4-054): vacuous-pass hazard. Every disconnect assertion in this
# file (and the pty tests above) checks `attr == screen._viewport_danger_attr`.
# If `_chrome_attr` and `_viewport_danger_attr` were EVER equal, all of
# those assertions would pass vacuously while the border silently signaled
# nothing at all. WO-P4-053's `_SharedPairs.attr_for` degrades ANY color it
# cannot allocate a pair for (process-lifetime pair-table exhaustion, or any
# other curses.error on init_pair) to the SAME curses.A_NORMAL fallback --
# so two DIFFERENT color names (info/cyan, danger/red) could in principle
# both land on that identical fallback.
# ---------------------------------------------------------------------------


def _patch_fake_curses_color_support(monkeypatch, screens_mod, *, color_pairs_limit):
    """Monkeypatch just enough of the real ``curses`` module (screens.py's
    own module-level ``curses`` reference) to drive ``_SharedPairs.attr_for``
    through its REAL allocation logic with ``has_colors()`` True and a
    controlled ``COLOR_PAIRS`` ceiling, without needing a live terminal --
    ``start_color``/``use_default_colors``/``init_pair`` all SUCCEED (unlike
    a plain pytest process with no ``initscr()``, where they'd raise
    ``curses.error`` immediately and mask the specific COLOR_PAIRS-exhaustion
    branch this probes), and ``color_pair(n)`` returns a distinct sentinel
    per pair number so two REAL allocations can never coincidentally compare
    equal. Also swaps in a fresh ``_SharedPairs`` instance so this test's
    allocation history can't leak into (or be polluted by) any other test's
    use of the module-level singleton.
    """
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: True)
    monkeypatch.setattr(screens_mod.curses, "start_color", lambda: None)
    monkeypatch.setattr(screens_mod.curses, "use_default_colors", lambda: None)
    monkeypatch.setattr(screens_mod.curses, "COLOR_PAIRS", color_pairs_limit, raising=False)
    monkeypatch.setattr(screens_mod.curses, "init_pair", lambda n, fg, bg: None)
    monkeypatch.setattr(screens_mod.curses, "color_pair", lambda n: 1000 + n)
    monkeypatch.setattr(screens_mod, "_shared_pairs", screens_mod._SharedPairs())


def test_shared_pair_exhaustion_reproduces_and_is_fixed_by_underline_interim(monkeypatch):
    """Empirical probe: with a small, deterministic COLOR_PAIRS ceiling (3)
    and the REAL app's own allocation order ahead of PlayShellScreen's
    construction (LauncherScreen's own ``_TonePalette`` 7-tone iteration,
    which every real launcher -> play navigation exercises first), does the
    collapse actually reproduce? Observed (see report): yes -- both
    info/cyan and danger/red exhaust the shared pair table and would
    otherwise return the identical ``curses.A_NORMAL`` fallback. The fix
    (``screens.py`` ``_init_colors``) detects that collapse and reuses the
    SAME mono-mode underline interim (``curses.A_UNDERLINE``) rather than
    inventing a second STATE convention."""
    from tw2002_aiclient import screens as screens_mod

    _patch_fake_curses_color_support(monkeypatch, screens_mod, color_pairs_limit=3)

    # Mirrors the real app's own construction order: LauncherScreen's
    # 7-tone palette always builds first (launcher -> play navigation),
    # consuming pairs for green/yellow before PlayShellScreen ever asks for
    # cyan/red.
    screens_mod._TonePalette()

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(FULL_ROWS, FULL_COLS), profile)

    assert screen._chrome_attr == curses.A_NORMAL, (
        "sanity: this test's premise is that chrome ALSO exhausts under this ceiling+order -- "
        f"got {screen._chrome_attr!r}; the exhaustion condition did not reproduce as expected"
    )
    assert screen._viewport_danger_attr == curses.A_UNDERLINE, (
        f"expected the collapse-guard fix to fall back to the mono interim underline, "
        f"got {screen._viewport_danger_attr!r}"
    )
    assert screen._viewport_danger_attr != screen._chrome_attr, (
        "the vacuous-pass hazard: chrome and danger attrs must never be equal"
    )


def test_danger_only_allocation_failure_still_gets_underline_interim(monkeypatch):
    """REVISE (team-lead, WO-P4-054): a narrower ``danger == chrome`` guard
    misses the state one allocation slot removed from the both-fail
    collapse above -- chrome's own allocation SUCCEEDS, danger's ALONE
    fails. That split requires chrome (info/cyan) to be requested and
    allocated BEFORE danger (danger/red) against a fresh, shared
    allocator -- ``PlayShellScreen._init_colors``'s own two lines request
    them in exactly that order, so this reproduces by constructing
    ``PlayShellScreen`` as the FIRST-EVER caller into a fresh
    ``_SharedPairs`` (skipping ``_TonePalette()``, unlike the sibling test
    above).

    Verified NOT reachable via the real app's own ``_run()`` entry point
    (``app.py``) today: ``LauncherScreen`` -- and therefore its own
    ``_TonePalette`` 7-tone iteration, which requests danger/red BEFORE
    info/cyan -- always constructs first, and allocation is monotonic (a
    failed request never advances the shared pointer), so under that real
    order danger can only fail at or before the same ceiling chrome does.
    This test exists as a defensive, construction-order-independent pin of
    the RULE canon actually states ("color unavailable" on the danger
    attr itself) rather than of a reachable live scenario -- proving the
    generalized ``self._viewport_danger_attr == curses.A_NORMAL`` guard
    doesn't quietly depend on which allocation happened first."""
    from tw2002_aiclient import screens as screens_mod

    _patch_fake_curses_color_support(monkeypatch, screens_mod, color_pairs_limit=2)

    # Deliberately NO _TonePalette() here -- PlayShellScreen must be the
    # first-ever consumer of this fresh allocator so its own chrome-then-
    # danger request order is what's exercised.
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(FULL_ROWS, FULL_COLS), profile)

    assert screen._chrome_attr != curses.A_NORMAL, (
        "sanity: this test's premise is that chrome ALONE succeeds under this ceiling+order -- "
        f"got {screen._chrome_attr!r}; the split-allocation condition did not reproduce as expected"
    )
    assert screen._viewport_danger_attr == curses.A_UNDERLINE, (
        "expected the generalized guard (danger attr tested directly, not compared to chrome) to "
        f"still catch a lone danger-allocation failure, got {screen._viewport_danger_attr!r}"
    )
    assert screen._viewport_danger_attr != screen._chrome_attr


def test_chrome_and_danger_attrs_are_never_equal_guard(monkeypatch):
    """Required regardless of whether exhaustion reproduces on any given
    terminal: pin chrome/danger as genuinely DISTINCT in mono mode AND in a
    REAL (non-exhausted, generously-sized) color-pair allocation -- this
    guard must fail loudly the instant that invariant breaks, closing the
    vacuous-pass hazard for good."""
    mono_screen = _make_screen(monkeypatch)
    assert mono_screen._chrome_attr != mono_screen._viewport_danger_attr

    from tw2002_aiclient import screens as screens_mod

    _patch_fake_curses_color_support(monkeypatch, screens_mod, color_pairs_limit=64)
    screens_mod._TonePalette()
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    color_screen = screens_mod.PlayShellScreen(_NullWin(FULL_ROWS, FULL_COLS), profile)
    assert color_screen._chrome_attr != color_screen._viewport_danger_attr
    # And neither is the underline-interim fallback value -- proves this
    # branch hit genuine distinct pair allocation, not the collapse-guard.
    assert color_screen._viewport_danger_attr != curses.A_UNDERLINE


# ---------------------------------------------------------------------------
# REVISE (Mack CRITICAL): pair-collision regression. Mirrors Mack's own PoC
# scenario (a launcher -> play -> Esc -> back round trip) as a real pytest,
# proving _SharedPairs (tw2002_aiclient/screens.py) fixes it -- one
# continuously-captured process, one LauncherScreen instance, colors
# snapshotted before entering play and re-checked after returning.
# ---------------------------------------------------------------------------

# TW2002_LAUNCHER_FIXTURE=polish (app.py's own _load_profiles fixture): a
# muted "steady" row, a warn "broken-pilot" (error) row, and an ok
# "armed-cap" (autopilot) row -- Mack's own PoC picked this fixture
# specifically because it exercises two DISTINCT non-chrome tones (warn +
# ok) in the same screen, both of which collided with PlayShellScreen's
# former pairs 1/2.
_ROUND_TRIP_BOOTSTRAP = r"""
import os
import sys

os.environ["TW2002_LAUNCHER_FIXTURE"] = "polish"
os.environ.pop("TW2002_LAUNCHER_DEMO", None)
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

_ROUND_TRIP_ROWS, _ROUND_TRIP_COLS = 30, 100


def _drive_pair_collision_round_trip(tmp_path: Path, timeout: float = 15.0) -> tuple[bytes, bytes]:
    """Spawn ``app._run`` (``polish`` launcher fixture) in one pty: capture
    a BASELINE snapshot of the initial launcher screen (before any key is
    sent), then navigate to the ``armed-cap`` row, Enter -> play, Esc ->
    back to the SAME ``LauncherScreen`` instance, and capture a final
    snapshot once the launcher is visible again. Returns
    ``(baseline_bytes, after_round_trip_bytes)`` -- both replayable
    independently via ``pyte_screen`` -- so a test can compare the SAME
    instance's cached row colors before vs. after a mid-session
    ``PlayShellScreen`` construction (Mack's own PoC scenario).

    ``TW_RUN_DIR`` points at an isolated tmp dir so this never touches the
    project's own ``run/twd.sock``.
    """
    bootstrap = tmp_path / "pair_collision_round_trip_bootstrap.py"
    bootstrap.write_text(_ROUND_TRIP_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, _ROUND_TRIP_ROWS, _ROUND_TRIP_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    env.pop("TW2002_ASCII", None)
    env.pop("TW2002_LAUNCHER_DEMO", None)
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
    baseline: bytes | None = None
    phase = "wait_launcher_initial"
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

            grid = pyte_grid(captured, _ROUND_TRIP_ROWS, _ROUND_TRIP_COLS)

            if phase == "wait_launcher_initial":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, "armed-cap"):
                    # Snapshot BEFORE any navigation key -- this is the real
                    # BASELINE render, never a later/corrupted one.
                    captured = _settle(master_fd, captured, 0.6)
                    baseline = captured
                    os.write(master_fd, b"jj")  # DOWN DOWN (vim keys) -> armed-cap
                    phase = "wait_selected"
            elif phase == "wait_selected":
                captured = _settle(master_fd, captured, 0.4)
                os.write(master_fd, b"\r")
                phase = "wait_play"
            elif phase == "wait_play":
                if find_text(grid, "PLAY SHELL"):
                    captured = _settle(master_fd, captured, 0.6)
                    os.write(master_fd, b"\x1b")  # Esc -> back to the SAME launcher instance
                    phase = "wait_back"
            elif phase == "wait_back":
                if find_text(grid, "SELECT PROFILE") and find_text(grid, "armed-cap"):
                    captured = _settle(master_fd, captured, 0.8)
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

    assert phase == "done" and baseline is not None, (
        f"pair-collision round-trip drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, _ROUND_TRIP_ROWS, _ROUND_TRIP_COLS))
    )
    return baseline, captured


@pytest.fixture(scope="module")
def _pair_collision_round_trip_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("pair_collision_round_trip")
    return _drive_pair_collision_round_trip(tmp_path)


@_PTY_SKIP
def test_launcher_row_colors_survive_a_play_shell_round_trip(_pair_collision_round_trip_capture):
    """Mack's CRITICAL PoC, pinned: the SAME LauncherScreen instance's
    already-cached warn/ok row colors must be byte-identical before and
    after a mid-session PlayShellScreen construction (launcher -> play ->
    Esc -> back). Before ``_SharedPairs``, this failed reproducibly --
    the warn row (``broken-pilot``) flipped from yellow/"brown" to red, and
    the ok row (``armed-cap``) flipped from green to cyan, because
    ``PlayShellScreen`` happened to reuse pairs 1/2 for its own
    info/danger colors."""
    baseline_bytes, after_bytes = _pair_collision_round_trip_capture
    baseline_screen = pyte_screen(baseline_bytes, _ROUND_TRIP_ROWS, _ROUND_TRIP_COLS)
    after_screen = pyte_screen(after_bytes, _ROUND_TRIP_ROWS, _ROUND_TRIP_COLS)

    baseline_grid = pyte_grid(baseline_bytes, _ROUND_TRIP_ROWS, _ROUND_TRIP_COLS)
    after_grid = pyte_grid(after_bytes, _ROUND_TRIP_ROWS, _ROUND_TRIP_COLS)

    warn_row = find_text(baseline_grid, "broken-pilot")
    ok_row = find_text(baseline_grid, "armed-cap")
    assert warn_row is not None and ok_row is not None, "fixture rows must be present in the baseline capture"
    warn_y, _warn_col = warn_row
    ok_y, _ok_col = ok_row
    # The same rows must still be present at the same y in the post-round-trip
    # grid too -- same fixture, same screen, nothing else should have moved.
    assert find_text(after_grid, "broken-pilot") == warn_row
    assert find_text(after_grid, "armed-cap") == ok_row

    warn_before = baseline_screen.buffer[warn_y][3]
    warn_after = after_screen.buffer[warn_y][3]
    ok_before = baseline_screen.buffer[ok_y][3]
    ok_after = after_screen.buffer[ok_y][3]

    assert warn_before.fg == "brown", f"sanity: expected the fixture's warn row baseline to be pyte's ANSI-yellow 'brown', got {warn_before.fg!r}"
    assert warn_after.fg == warn_before.fg, (
        f"warn row color corrupted by the play-shell round trip: baseline fg={warn_before.fg!r}, "
        f"after fg={warn_after.fg!r} (Mack's PoC observed a flip to 'red')"
    )
    assert warn_after.bold == warn_before.bold

    assert ok_before.fg == "green", f"sanity: expected the fixture's ok row baseline to be green, got {ok_before.fg!r}"
    assert ok_after.fg == ok_before.fg, (
        f"ok row color corrupted by the play-shell round trip: baseline fg={ok_before.fg!r}, "
        f"after fg={ok_after.fg!r} (Mack's PoC observed a flip to 'cyan')"
    )
    assert ok_after.bold == ok_before.bold
