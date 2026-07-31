"""WO-P3-041 wire -- LOGS band advancing transcript tail + newest-row flash,
Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
LOGS band ``screens.py``/``app.py`` produce once wired to
``cockpit.logsband``: the box shows the daemon's ``status["log_tail"]``
content (not just the bare box title), the honest-empty/``status_line``
fallback still works with no ``log_tail`` field at all, and Esc/q
regression is unchanged. Layer-A coverage for the composer itself
(``compose_logs_lines``/``newest_tail_entry``/``flash_active``) lives in
``tests/test_cockpit_logsband.py``; this file only proves the
``PlayShellScreen``/``app.py`` wiring around it -- mirrors
``tests/test_cockpit_hud_pty.py``'s split for HUD.

WO-PLAY-STRIP-TRAINER-CHROME / DECISION
``RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`` point 4 routed
``status_line`` (offers/outcomes, previously a mid-control-strip
``status_offer`` segment) INTO this same LOGS box. At the real MIN_LINES
floor LOGS has exactly ONE content row, so a non-empty ``status_line``
reserves that row over a real tail rather than the two ever sharing it --
see ``screens.py``'s own ``reserve_status_row`` comment. Because the real
``app._run_play`` flow sets a non-empty, never-cleared ``status_line``
immediately after every successful ``ensure_session`` (the fixtures below
all stub a successful ensure), a full end-to-end drive through this file's
own subprocess bootstrap can no longer observe raw ``log_tail`` content at
all once a real tail exists -- only the reserved status row is visible.
Consequently:
  - the pty-level fixtures/tests that used to assert on raw tail text
    (the STATIC tail's own line, the growing ``advancing-line-N`` text, the
    redacted SECRET marker, the hostile-control-char tail payload) now
    assert on the reserved status row instead, or were converted to
    unit-level ``draw()`` calls (via ``_make_screen``/``_RecordingWin``)
    where ``status_line`` is directly controllable -- the only way left to
    exercise "an empty status_line + a real tail" now that a full
    subprocess drive can no longer reach that combination;
  - genuine tail-advancement + flash-timing over real draws is proven at
    the unit level in
    ``test_flash_state_persists_across_unchanged_newest_then_resets_on_change``
    (a manually-driven fake clock, not wall-clock ticks);
  - what the "advancing" pty fixture still uniquely proves is that the
    reserved status row stays stable and non-flashing across real ~1Hz
    ticks even while a REAL, continuously-growing tail sits underneath it
    (``test_status_row_never_flashes_while_the_underlying_tail_keeps_advancing``),
    exercising the ``flash_index`` guard end-to-end.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process (same convention as every sibling cockpit-panel pty suite), and
``TW_RUN_DIR`` always points at an isolated per-test tmp directory -- the
real ``status_provider`` (``app._daemon_status_provider``) is free to run
unstubbed against that empty dir (its own ``send_request`` early-returns
``daemon_not_running`` without ever opening a socket) for the no-fixture
scenario, and every other fixture additionally monkeypatches
``tw2002_aiclient.session.cli.send_request`` inside the bootstrap -- never
``run/twd.sock`` either way.
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


import curses

from tw2002_aiclient.cockpit.layout import frame_layout

from .pty_helpers import (
    find_text,
    pty_curses_supported,
    pyte_grid,
    pyte_screen,
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# Full tier -- matches every sibling cockpit-panel pty suite's own FULL
# constants so the LOGS band's one content row is unambiguously visible.
FULL_ROWS, FULL_COLS = 40, 160

_SECRET_MARKER = "<<secret input redacted>>"  # tw2002_aiclient.session.transcript_tail.TranscriptTail.append_redacted()'s own default wire format
_SECRET_SENTINEL = "SENTINEL-hunter2-SENTINEL"

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as every sibling cockpit-panel pty suite's own bootstrap. The
# "advancing" fixture keeps its own per-process call counter so log_tail
# genuinely GROWS between polls (real ~1Hz redraw ticks -- see the module
# docstring).
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

_LOGS_FIXTURE = os.environ.get("TW2002_TEST_LOGS_FIXTURE", "")
if _LOGS_FIXTURE:
    from tw2002_aiclient.session import cli as session_cli

    _state = {{"calls": 0}}

    def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        if verb != "status":
            return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}
        _state["calls"] += 1
        n = _state["calls"]

        if _LOGS_FIXTURE == "advancing":
            # Grows by one real entry every poll -- newest is always
            # "advancing-line-{{n}}", strictly larger than the previous
            # poll's, so every draw against this fixture is a fresh
            # arrival (see module docstring's flash-proof rationale).
            tail = [f"advancing-line-{{i}}" for i in range(1, n + 1)]
            return {{"ok": True, "connected": True, "idle_ms": 100, "log_tail": tail}}
        if _LOGS_FIXTURE == "static":
            return {{
                "ok": True,
                "connected": True,
                "idle_ms": 100,
                "log_tail": ["static-tail-line"],
            }}
        if _LOGS_FIXTURE == "secret":
            return {{
                "ok": True,
                "connected": True,
                "idle_ms": 100,
                "log_tail": ["before-secret", {secret_marker!r}],
                # Sentinel planted in an UNRELATED status field -- never
                # part of log_tail -- proving it cannot leak into the LOGS
                # band's own drawn row even though it rides the same
                # status payload.
                "prompt": {secret_sentinel!r},
            }}
        if _LOGS_FIXTURE == "hostile_control_chars":
            return {{
                "ok": True,
                "connected": True,
                "idle_ms": 100,
                "log_tail": ["before\nBREAKOUT-AFTER-NEWLINE"],
            }}
        return {{"ok": False, "error": "unknown_test_fixture"}}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
""".replace("{secret_marker!r}", repr(_SECRET_MARKER)).replace(
    "{secret_sentinel!r}", repr(_SECRET_SENTINEL)
)


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining ``master_fd`` for ``seconds`` of wall time, accumulating
    onto ``captured`` -- a single post-condition ``read()`` isn't reliable
    (``PlayShellScreen.draw()``'s one ``refresh()`` call still spans
    multiple OS-level pty read chunks for a full frame; LOGS is drawn near
    the end of the pass), same helper shape as
    ``tests/test_cockpit_liveness_pty.py``/``tests/test_cockpit_tones_pty.py``'s
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


def _spawn(tmp_path: Path, bootstrap_name: str, fixture: str) -> tuple[subprocess.Popen, int]:
    bootstrap = tmp_path / bootstrap_name
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, FULL_ROWS, FULL_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if fixture:
        env["TW2002_TEST_LOGS_FIXTURE"] = fixture
    else:
        env.pop("TW2002_TEST_LOGS_FIXTURE", None)
    env.pop("TW2002_ASCII", None)
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


def _teardown(proc: subprocess.Popen, master_fd: int, captured: bytes) -> bytes:
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
    return captured


def _drive_logs_pty(
    tmp_path: Path, *, ready_text: str, fixture: str = "", timeout: float = 14.0
) -> bytes:
    """Spawn ``app._run`` in a ``FULL_ROWS``x``FULL_COLS`` pty: Enter from
    the launcher once its chrome is up, capture the play-shell cockpit
    frame once ``ready_text`` is visible ANYWHERE on screen (letting at
    least one ~1 Hz refresh tick fully settle after that), then quit.

    ``ready_text`` must be real fixture CONTENT (a distinguishing tail
    line), never the bare "LOGS"/"PLAY SHELL" box title, which paints on
    the FIRST frame regardless of whether the status_provider's data has
    reached the composer yet (the WO-P3-038/039 lesson, mirrored from
    ``tests/test_cockpit_tones_pty.py``'s own ``_drive_tone_pty``).

    ``TW_RUN_DIR`` always points at an isolated tmp dir under ``tmp_path``
    so the real (unstubbed) status_provider path can never reach the
    project's own ``run/twd.sock`` regardless of which fixture is active.
    """
    proc, master_fd = _spawn(
        tmp_path, f"logs_pty_bootstrap_{fixture or 'none'}.py", fixture
    )

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

            grid = pyte_grid(captured, FULL_ROWS, FULL_COLS)

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
        captured = _teardown(proc, master_fd, captured)

    assert phase == "done", (
        f"pty logs drive stalled in phase={phase!r} fixture={fixture!r}; "
        "last grid:\n" + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return captured


def _drive_advancing_logs_pty(tmp_path: Path, timeout: float = 16.0) -> tuple[bytes, bytes]:
    """Spawn ``app._run`` with the "advancing" fixture. Captures an EARLY
    frame (shortly after the LOGS row first shows content, with only a
    short 0.5s settle -- comfortably under ``TICKER_FLASH_DURATION_S`` so
    an unguarded flash decision at this point would still read as a fresh
    arrival) and a LATER frame (after several more real ~1Hz ticks), both
    independently replayable.

    WO-PLAY-STRIP-TRAINER-CHROME: this fixture's tail keeps growing
    underneath (``advancing-line-N``), but the real ``app._run_play`` flow
    sets a non-empty, never-cleared ``status_line`` right after
    ``ensure_session`` -- see ``_static_capture``'s own comment -- which
    wins LOGS' one content row at the real MIN_LINES floor. So this drive
    no longer waits for (and the two tests below no longer assert on) the
    raw ``advancing-line-N`` text itself; genuine tail advancement + flash
    timing is proven at the unit level instead
    (``test_flash_state_persists_across_unchanged_newest_then_resets_on_change``).
    What THIS pty drive still uniquely proves: across a real subprocess
    with a REAL, continuously-growing tail underneath, the reserved status
    row stays stable and never flashes (see
    ``test_status_row_never_flashes_while_the_underlying_tail_keeps_advancing``
    below) -- exercising the ``flash_index`` guard end-to-end, not just in
    an isolated unit test.
    """
    proc, master_fd = _spawn(tmp_path, "logs_pty_bootstrap_advancing.py", "advancing")

    captured = b""
    capture_early: bytes | None = None
    capture_later: bytes | None = None
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
                    phase = "wait_first"
            elif phase == "wait_first":
                if find_text(grid, "session ready"):
                    captured = _settle(master_fd, captured, 0.5)
                    capture_early = captured
                    phase = "wait_growth"
            elif phase == "wait_growth":
                # Several more real ~1Hz ticks -- the underlying tail
                # keeps growing across this window even though the
                # reserved status row (proven stable/non-flashing by the
                # consuming test) is all that is visible.
                captured = _settle(master_fd, captured, 2.5)
                capture_later = captured
                os.write(master_fd, b"q")
                phase = "done"
                break
        if phase != "done":
            try:
                os.write(master_fd, b"q")
            except OSError:
                pass
    finally:
        captured = _teardown(proc, master_fd, captured)

    assert phase == "done" and capture_early is not None and capture_later is not None, (
        f"pty advancing-logs drive stalled in phase={phase!r}; last grid:\n"
        + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return capture_early, capture_later


@pytest.fixture(scope="module")
def _no_daemon_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_no_daemon")
    # No fixture -> status_provider resolves to None (daemon_not_running,
    # never touching run/twd.sock) -> no real tail -> the status_line
    # fallback (the real app._run_play flow sets
    # status_line = f"session ready — {classification}").
    return _drive_logs_pty(tmp_path, ready_text="session ready")


@pytest.fixture(scope="module")
def _static_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_static")
    # WO-PLAY-STRIP-TRAINER-CHROME: the real `app._run_play` flow always
    # sets a non-empty `status_line` right after `ensure_session` succeeds
    # (the "session ready — <classification>" line, or -- since this
    # fixture's classification is `main_command`, matching
    # `app._EXPLORE_OFFER_CLASSIFICATION` -- the explore-offer prose that
    # supersedes it), and never clears it back to "" on its own. At the
    # real MIN_LINES floor LOGS has exactly one content row, so that
    # status line -- not the fixture's own "static-tail-line" tail entry
    # -- is what a full end-to-end drive actually shows. See
    # ``test_logs_title_visible_and_status_line_wins_the_reserved_row``
    # below; raw tail-rendering itself is proven at the unit level
    # (``test_real_tail_renders_when_status_line_is_empty``) where
    # `status_line` is directly controllable.
    return _drive_logs_pty(tmp_path, ready_text="session ready", fixture="static")


@pytest.fixture(scope="module")
def _advancing_captures(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("logs_advancing")
    return _drive_advancing_logs_pty(tmp_path)


def _logs_content_row(regions: dict) -> int:
    logs = regions["logs"]
    return logs["y"] + 1  # LOGS' one content row at the real MIN_LINES floor


# ---------------------------------------------------------------------------
# (a) LOGS title + a non-secret real tail line visible in the band. Also
# pins the flash NEGATIVE case: a STATIC tail, captured well past its
# one-time arrival, is NOT bold (contrasts with the always-advancing
# positive case below).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_logs_title_visible_and_status_line_wins_the_reserved_row(_static_capture):
    """DECISION point 4: `status_line` routes into LOGS. At the real
    MIN_LINES floor it wins the box's only row over a real tail rather
    than the two ever sharing it -- see the fixture's own comment. The
    static fixture's own tail text is therefore NOT expected to be
    visible here (that would be the pre-WO behavior this WO retired)."""
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    logs = regions["logs"]
    row = _logs_content_row(regions)
    grid = pyte_grid(_static_capture, FULL_ROWS, FULL_COLS)

    assert "LOGS" in grid[logs["y"]]
    assert "session ready" in grid[row]
    assert "static-tail-line" not in grid[row]

    screen = pyte_screen(_static_capture, FULL_ROWS, FULL_COLS)
    cell = screen.buffer[row][logs["x"] + 1]
    assert not cell.bold, (
        "the reserved status row is chrome, not a transcript arrival, "
        "and must never flash bold"
    )


# ---------------------------------------------------------------------------
# (b) Advancing tail underneath a reserved status row -- WO-PLAY-STRIP-
# TRAINER-CHROME retired the pre-WO "raw advancing-line-N text is directly
# visible in LOGS" proof (see ``_drive_advancing_logs_pty``'s own comment
# for why that is no longer observable through a full app.py drive; the
# genuine-advancement + flash-timing proof it duplicated now lives at the
# unit level in
# ``test_flash_state_persists_across_unchanged_newest_then_resets_on_change``).
# What a real subprocess uniquely adds is proven here instead: with a REAL,
# continuously-growing tail underneath (this fixture's own defining trait),
# the reserved status row that wins LOGS' one row stays textually stable
# and never flashes bold -- exercising the ``flash_index`` guard end-to-end
# rather than in isolation.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_status_row_never_flashes_while_the_underlying_tail_keeps_advancing(
    _advancing_captures,
):
    capture_early, capture_later = _advancing_captures
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    logs = regions["logs"]
    content_col = logs["x"] + 1

    for label, capture in (("early", capture_early), ("later", capture_later)):
        grid = pyte_grid(capture, FULL_ROWS, FULL_COLS)
        assert "session ready" in grid[row], (
            f"expected the reserved status row at the {label} capture, "
            f"got {grid[row]!r}"
        )
        assert "advancing-line-" not in grid[row], (
            f"the underlying tail keeps growing but must not surface over "
            f"the reserved status row at the {label} capture, got {grid[row]!r}"
        )
        screen = pyte_screen(capture, FULL_ROWS, FULL_COLS)
        cell = screen.buffer[row][content_col]
        assert not cell.bold, (
            f"the reserved status row is chrome, not a transcript arrival, "
            f"and must never flash bold even while the tail keeps advancing "
            f"underneath it -- {label} capture got bold={cell.bold!r}"
        )


# ---------------------------------------------------------------------------
# (c) SECRET: the pre-redacted marker renders in the band; a sentinel
# planted in an UNRELATED status field never reaches the LOGS band's own
# row. WO-PLAY-STRIP-TRAINER-CHROME: this moved from a full pty drive to a
# unit-level draw() -- see ``_static_capture``'s own comment for why the
# real ``app._run_play`` flow can no longer reach a state with a real tail
# AND an empty ``status_line`` simultaneously (status_line always wins the
# one reserved row once ensure succeeds), so a full end-to-end pty drive
# can no longer observe raw tail content at all. Direct control of
# ``status_line`` here keeps this security-relevant proof (redaction
# reaching the actually-drawn row) alive at the layer that can still see
# it.
# ---------------------------------------------------------------------------


def test_secret_marker_present_and_sentinel_absent_from_logs_row(monkeypatch):
    screen, win = _make_screen(monkeypatch)
    screen.status_line = ""
    screen.status_provider = lambda: {
        "connected": True,
        "idle_ms": 1,
        "log_tail": ["before-secret", _SECRET_MARKER],
        # Sentinel planted in an UNRELATED status field -- never part of
        # log_tail -- proving it cannot leak into the LOGS band's own row
        # even though it rides the same status payload.
        "prompt": _SECRET_SENTINEL,
    }
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert _SECRET_MARKER in row_calls[-1], (
        f"expected the pre-redacted marker in the LOGS band row, got {row_calls[-1]!r}"
    )
    offenders = [text for (_y, _x, text, _attr) in win.calls if _SECRET_SENTINEL in text]
    assert not offenders, (
        "a sentinel planted in an UNRELATED status field ('prompt') must never "
        f"leak into any drawn row, found in: {offenders!r}"
    )


# ---------------------------------------------------------------------------
# (d) Honest-empty / status_line fallback: no log_tail field at all -- the
# ensure-session status_line renders instead of a bare "(none yet)".
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_no_log_tail_field_falls_back_to_status_line(_no_daemon_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    grid = pyte_grid(_no_daemon_capture, FULL_ROWS, FULL_COLS)

    assert "session ready" in grid[row], (
        f"expected the ensure-session status_line fallback in the LOGS band, got {grid[row]!r}"
    )
    assert "(none yet)" not in grid[row]


# ---------------------------------------------------------------------------
# (e) Esc -> back / q -> quit unchanged -- the LOGS wiring adds no new key
# handling. Mirrors every sibling pty suite's own regression leg.
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
    # `ord(" ")` (Space) dropped from this list -- WO-AUTOLOOP-RELAUNCH-COCKPIT
    # legitimately binds it to the pause intent; this pin is only about
    # THIS module's own wiring not adding new key handling.
    for key in (curses.KEY_UP, curses.KEY_DOWN, ord("1"), ord("d")):
        assert screen.handle_key(key) is None


# ---------------------------------------------------------------------------
# (f) Hostile control-char payload inside a tail line is neutralized before
# it ever reaches ``addstr`` -- the shared draw choke point
# (``cockpit.draw._safe_write``, exercised via ``draw_lines_attrs`` here,
# the same call LOGS itself makes). WO-PLAY-STRIP-TRAINER-CHROME: moved
# from a full pty drive to a unit-level draw() for the same reason as the
# SECRET test above (a full ``app._run_play`` drive can no longer reach a
# real tail with an empty ``status_line``). The REAL curses/terminal
# round-trip proof for this exact neutralization already exists at both
# ``tests/test_cockpit_frame_pty.py::test_embedded_newline_in_status_line_does_not_escape_box``
# (status_line, full pty) and this file's own
# ``tests/test_cockpit_logsband_pty.py`` unit-level ``draw_lines_attrs``
# proof pattern -- this test only additionally pins that LOGS' own wiring
# passes tail content through that same choke point.
# ---------------------------------------------------------------------------


def test_embedded_newline_in_tail_line_is_neutralized_before_addstr(monkeypatch):
    screen, win = _make_screen(monkeypatch)
    screen.status_line = ""
    screen.status_provider = lambda: {
        "connected": True,
        "idle_ms": 1,
        "log_tail": ["before\nBREAKOUT-AFTER-NEWLINE"],
    }
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    # The sanitized `\n` becomes a plain space -- content stays on ONE
    # `addstr` call, never a second call implying a moved cursor/row.
    assert "\n" not in row_calls[-1]
    assert "before BREAKOUT-AFTER-NEWLINE" in row_calls[-1]
    # The next row belongs to other chrome (e.g. the box's own bottom
    # border) and legitimately receives its own unrelated addstr calls --
    # what must never happen is the tail's own payload bleeding onto it.
    next_row_calls = [text for (y, _x, text, _attr) in win.calls if y == row + 1]
    assert not any("BREAKOUT" in text for text in next_row_calls), (
        f"a neutralized embedded newline must never bleed onto the next row, "
        f"got {next_row_calls!r}"
    )


# ---------------------------------------------------------------------------
# Poll-guard: LOGS is a SEVENTH consumer of the same shared
# status_provider() snapshot -- still exactly one poll per draw() at the
# full tier, mirroring every sibling poll-guard test in this suite family.
# ---------------------------------------------------------------------------


def test_poll_guard_still_fires_exactly_once_with_logs_consuming_the_snapshot(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    assert regions["logs"] is not None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _NullWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"connected": True, "idle_ms": 1, "log_tail": ["a", "b"]}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one status_provider poll with LOGS consuming the same "
        f"snapshot, got {len(calls)}"
    )


# ---------------------------------------------------------------------------
# Unit-level: flash-state tracking / status_line fallback / hostile
# now_fn -- no pty/curses needed, mirrors
# tests/test_cockpit_liveness_pty.py's own unit-level now_fn seam proofs.
# ---------------------------------------------------------------------------


class _RecordingWin(_NullWin):
    def __init__(self, rows: int, cols: int) -> None:
        super().__init__(rows, cols)
        self.calls: list[tuple[int, int, str, int]] = []

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))


def _make_screen(monkeypatch, *, now_fn=None):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile, now_fn=now_fn)
    return screen, win


def test_status_line_fallback_used_when_no_real_tail(monkeypatch):
    screen, win = _make_screen(monkeypatch)
    screen.status_line = "session ready — main_command"
    screen.status_provider = lambda: {"connected": True, "idle_ms": 1}  # no log_tail
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls, "expected an addstr call on the LOGS content row"
    assert "session ready" in row_calls[-1]
    assert "(none yet)" not in row_calls[-1]


def test_status_line_reserves_the_one_row_over_a_real_tail(monkeypatch):
    """WO-PLAY-STRIP-TRAINER-CHROME / DECISION
    ``RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`` point 4: at the real
    MIN_LINES floor (``logs_inner_h == 1``) there is no room to show both a
    real tail line and ``status_line`` -- the status line wins the box's
    one row (this is the opposite of the pre-WO
    WO-PLAY-OFFER-VISIBLE-ON-LIVE-era pin this test replaces, which is now
    intentionally inverted: `status_offer` used to be a mid-strip segment
    ADDITIONAL to LOGS' own tail; now it rides INSIDE LOGS' only row)."""
    screen, win = _make_screen(monkeypatch)
    screen.status_line = "session ready — main_command"
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["real tail line"],
    }
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert "session ready" in row_calls[-1]
    assert "real tail line" not in row_calls[-1]


def test_real_tail_renders_when_status_line_is_empty(monkeypatch):
    """The tail-rendering path itself is unchanged -- it is only ever
    displaced by a NON-empty ``status_line`` (see the reservation test
    above). Empty ``status_line`` is the ordinary steady state once the
    ensure-session/offer prose has been superseded by a later empty
    assignment, so real tail content must still surface then."""
    screen, win = _make_screen(monkeypatch)
    screen.status_line = ""
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["real tail line"],
    }
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert "real tail line" in row_calls[-1]


def test_flash_state_persists_across_unchanged_newest_then_resets_on_change(monkeypatch):
    clock = {"t": 0.0}
    screen, win = _make_screen(monkeypatch, now_fn=lambda: clock["t"])
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["only line"],
    }

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)

    # First draw at t=0.0 -- fresh arrival, must flash bold.
    screen.draw()
    row_calls = [(text, attr) for (y, _x, text, attr) in win.calls if y == row]
    assert row_calls
    assert row_calls[-1][1] & curses.A_BOLD

    # Second draw, same content, well past the flash duration -- must NOT
    # still be bold (the arrival timestamp is not reset by an unchanged
    # newest entry).
    win.calls.clear()
    clock["t"] = 5.0
    screen.draw()
    row_calls = [(text, attr) for (y, _x, text, attr) in win.calls if y == row]
    assert row_calls
    assert not (row_calls[-1][1] & curses.A_BOLD)

    # Third draw, a genuinely NEW newest entry arrives at t=5.0 -- must
    # flash again.
    win.calls.clear()
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["only line", "new line"],
    }
    screen.draw()
    row_calls = [(text, attr) for (y, _x, text, attr) in win.calls if y == row]
    assert row_calls
    assert "new line" in row_calls[-1][0]
    assert row_calls[-1][1] & curses.A_BOLD


def test_flash_state_resets_when_tail_reverts_to_honest_empty(monkeypatch):
    clock = {"t": 0.0}
    screen, win = _make_screen(monkeypatch, now_fn=lambda: clock["t"])

    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["real line"],
    }
    screen.draw()
    assert screen._logs_last_newest == "real line"
    assert screen._logs_newest_arrival_s == 0.0

    # Tail reverts to empty (e.g. daemon restart) -- tracking resets sanely,
    # never leaves a stale arrival timestamp pointing at vanished content.
    screen.status_provider = lambda: {"connected": True, "idle_ms": 1}
    clock["t"] = 1.0
    screen.draw()
    assert screen._logs_last_newest is None
    assert screen._logs_newest_arrival_s is None


def test_raising_now_fn_does_not_crash_draw_and_logs_still_renders(monkeypatch):
    """Mirrors tests/test_cockpit_liveness_pty.py's own raising-now_fn
    proof: a raising now_fn (a public __init__ kwarg) must not escape
    draw(), and the LOGS content must still render (real content, not a
    crash) -- the flash decision itself degrades to "not flashing" rather
    than taking the draw pass down with it."""
    def _raising_now_fn():
        raise RuntimeError("clock seam is broken")

    screen, win = _make_screen(monkeypatch, now_fn=_raising_now_fn)
    screen.status_provider = lambda: {
        "connected": True, "idle_ms": 1, "log_tail": ["still here"],
    }

    screen.draw()  # must not raise

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert "still here" in row_calls[-1]


def test_raising_status_provider_falls_back_to_honest_state(monkeypatch):
    screen, win = _make_screen(monkeypatch)

    def _raising_provider():
        raise RuntimeError("daemon socket exploded")

    screen.status_provider = _raising_provider
    screen.status_line = ""
    screen.draw()  # must not raise

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    row = _logs_content_row(regions)
    row_calls = [text for (y, _x, text, _attr) in win.calls if y == row]
    assert row_calls
    assert "(none yet)" in row_calls[-1]
