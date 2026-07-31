"""WO-P4-052, lane B -- GAME viewport LIVE PAINT, real-curses pty proof.

PWO-051 proved the bordered viewport SHELL (border/title/honest-blank
interior, ``tests/test_cockpit_viewport_pty.py``). This WO wires the actual
content: ``cockpit/viewport.py::compose_viewport_lines`` turns a
``WatchFeed`` settle-edge event's ``event["screen"]`` rows into the box's
interior lines, and ``PlayShellScreen.draw()`` paints them through the same
``cockpit_draw.draw_lines`` choke point every other panel uses. This file
proves the *drawn* result at real curses + pyte replay -- assertions read
pyte grid text and ``screen.buffer[r][c]``/``screen.title`` only, never an
ANSI-escape regex (house pty law).

No live daemon anywhere: ``adapters.ensure_session`` is stubbed (matches
every sibling cockpit-panel pty suite), and ``app.WatchFeed`` itself is
replaced inside the spawned process with a fake whose ``snapshot()``
returns a scripted, STATIC ``WatchFeedSnapshot``-shaped object (``events_
received``/``latest_event``/``running``) -- ``start``/``stop`` are no-ops,
mirroring ``tests/test_watchfeed_wire.py``'s ``_RecordingFeed`` double.
``TW_RUN_DIR`` always points at an isolated per-test tmp dir so the real
(unstubbed) ``status_provider`` path can never reach the project's own
``run/twd.sock`` either way -- same convention as every sibling cockpit
pty suite.

Ready-text marker: because each fixture below is a STATIC payload (the fake
feed returns the identical snapshot on every poll -- no per-process call
counter needed, unlike LOGS' advancing-tail fixture), every content-bearing
fixture waits on its OWN injected game content as the ready marker (a
distinctive string that cannot occur in chrome), never the bare "GAME" box
title, which paints on the very first frame before ``viewport_provider`` is
even wired (the WO-P3-038/039 lesson, mirrored from every sibling suite).
The two honest-blank fixtures (no game content to wait on) fall back to
the LOGS band's own honest-empty ``status_line`` marker ("session ready"),
exactly as ``tests/test_cockpit_viewport_pty.py``'s original shell proof
already does.
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


from tw2002_aiclient.cockpit.layout import GAME_H, GAME_W, frame_layout

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

# Full tier only (matches every sibling cockpit-panel pty suite's own FULL
# constants) -- interior is exactly GAME_W x GAME_H (80x25) here, per
# layout.py's own "bordered viewport wraps the daemon's true native pyte
# grid, zero inset" invariant.
FULL_ROWS, FULL_COLS = 40, 160

_READY_TEXT = "session ready"  # LOGS band's honest-empty status_line fallback

# Fixture content -- mirrored verbatim inside the spawned bootstrap's own
# _FIXTURE_EVENTS dict below so assertions never re-derive what was sent.
_CONTENT_ROWS = ["ZQX-SECTOR-4223", "PAINT-ROW-B", "PAINT-ROW-C", "PAINT-ROW-D", "PAINT-ROW-E"]
_OVERFLOW_ROWS = ["OVFL-" + str(i).zfill(2) for i in range(30)]  # 30 > GAME_H(25) -- forces TOP-DROP
_HOSTILE_MARKER = "HOSTILE-MARK"
# After cockpit.draw's control-char neutralization (ESC/BEL -> space,
# alignment-preserving), the CSI/OSC payload below becomes literal,
# harmless text ("[31mRED", "]0;evil-title") rather than an executed
# escape sequence -- see this file's own hostile test for the exact
# post-sanitize string this was hand-verified against.
_HOSTILE_SANITIZED_FRAGMENT = "[31mRED"

_DOUBLE_GLYPHS_UNICODE = ("╔", "╗", "╚", "╝")

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as every sibling cockpit-panel pty suite's own bootstrap, plus
# a fixture-selected fake `app.WatchFeed` (WO-P4-050's real class is never
# touched -- only the name `app.py` binds it to is replaced, mirroring
# `tests/test_watchfeed_wire.py`'s own recording-double idiom). Uses a
# plain `__PROJECT_ROOT__` token + `.replace()` rather than `.format()` so
# the fixture dict's own braces below never need doubling.
_BOOTSTRAP = r'''
import os
import sys

os.environ["TW2002_LAUNCHER_DEMO"] = "1"
os.environ.pop("TW2002_HANDOFF_SMOKE", None)
os.environ.pop("TW2002_LAUNCHER_SMOKE", None)
os.environ.pop("TW2002_BANK_SMOKE", None)

sys.path.insert(0, __PROJECT_ROOT__)

from tw2002_aiclient import adapters
from tw2002_aiclient.adapters import EnsureResult


def _fake_ensure(profile, **kwargs):
    return EnsureResult(ok=True, classification="unknown")  # no App-armed explore kick in chrome PTY


adapters.ensure_session = _fake_ensure

_VIEWPORT_FIXTURE = os.environ.get("TW2002_TEST_VIEWPORT_FIXTURE", "")
if _VIEWPORT_FIXTURE:
    import tw2002_aiclient.app as app_mod

    _FIXTURE_EVENTS = {
        "content": {"screen": [
            "ZQX-SECTOR-4223",
            "PAINT-ROW-B",
            "PAINT-ROW-C",
            "PAINT-ROW-D",
            "PAINT-ROW-E",
        ]},
        "overflow": {"screen": ["OVFL-" + str(i).zfill(2) for i in range(30)]},
        "empty_none": None,
        "empty_list": {"screen": []},
        "hostile": {"screen": [
            "HOSTILE-MARK \x1b[31mRED\x1b[0m \x1b]0;evil-title\x07TAIL",
        ]},
    }
    _event = _FIXTURE_EVENTS.get(_VIEWPORT_FIXTURE)

    class _FakeSnapshot:
        def __init__(self, latest_event):
            self.events_received = 1 if latest_event is not None else 0
            self.latest_event = latest_event
            self.running = True

    class _FakeWatchFeed:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def snapshot(self):
            return _FakeSnapshot(_event)

    app_mod.WatchFeed = _FakeWatchFeed

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
'''


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining ``master_fd`` for ``seconds`` of wall time -- a single
    post-condition ``read()`` isn't reliable (``PlayShellScreen.draw()``'s
    one ``refresh()`` call still spans multiple OS-level pty read chunks
    for a full frame), same helper shape as every sibling cockpit-panel pty
    suite's own ``_settle``."""
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
    bootstrap.write_text(
        _BOOTSTRAP.replace("__PROJECT_ROOT__", repr(str(PROJECT_ROOT))), encoding="utf-8"
    )
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, FULL_ROWS, FULL_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if fixture:
        env["TW2002_TEST_VIEWPORT_FIXTURE"] = fixture
    else:
        env.pop("TW2002_TEST_VIEWPORT_FIXTURE", None)
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


def _drive_viewport_paint_pty(
    tmp_path: Path, *, fixture: str, ready_text: str, timeout: float = 14.0
) -> bytes:
    """Spawn ``app._run`` in a ``FULL_ROWS``x``FULL_COLS`` pty: Enter from
    the launcher once its chrome is up, capture the play-shell cockpit
    frame once ``ready_text`` is visible ANYWHERE on screen (settling
    briefly after that so the same draw pass's GAME-panel writes have
    fully landed), then quit."""
    proc, master_fd = _spawn(
        tmp_path, f"viewport_paint_pty_bootstrap_{fixture or 'none'}.py", fixture
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
        f"pty viewport-paint drive stalled in phase={phase!r} fixture={fixture!r}; "
        "last grid:\n" + "\n".join(pyte_grid(captured, FULL_ROWS, FULL_COLS))
    )
    return captured


def _interior(center: dict) -> tuple[int, int, int, int]:
    """``(y, x, w, h)`` of a bordered region's own interior -- inset by one
    cell on every side, matching ``cockpit_draw.draw_lines``'s own
    ``boxed=True`` inset math."""
    y, x, w, h = center["y"], center["x"], center["w"], center["h"]
    return y + 1, x + 1, w - 2, h - 2


def _assert_bordered_interior_blank(grid: list[str], center: dict) -> None:
    inner_y, inner_x, inner_w, inner_h = _interior(center)
    for row in range(inner_y, inner_y + inner_h):
        segment = grid[row][inner_x : inner_x + inner_w]
        assert segment == " " * inner_w, (
            f"expected GAME interior row {row} blank across {inner_w} cols, got {segment!r}"
        )


def _assert_double_border_corners(screen, center: dict) -> None:
    tl_g, tr_g, bl_g, br_g = _DOUBLE_GLYPHS_UNICODE
    y, x, w, h = center["y"], center["x"], center["w"], center["h"]
    assert screen.buffer[y][x].data == tl_g
    assert screen.buffer[y][x + w - 1].data == tr_g
    assert screen.buffer[y + h - 1][x].data == bl_g
    assert screen.buffer[y + h - 1][x + w - 1].data == br_g


# ---------------------------------------------------------------------------
# (a) Distinctive fixture content lands inside the GAME interior, at a
# genuine interior cell -- not merely somewhere on the grid.
# (b) Multi-row fidelity: several scripted rows land on consecutive
# interior rows in order, top-left anchored (first fixture row on the
# interior's own first row/column).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _content_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_paint_content")
    return _drive_viewport_paint_pty(tmp_path, fixture="content", ready_text=_CONTENT_ROWS[0])


@_PTY_SKIP
def test_distinctive_marker_lands_inside_game_interior_cell_range(_content_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert center is not None and center["border"] is True
    inner_y, inner_x, inner_w, inner_h = _interior(center)
    # Sanity-pin: at the full tier the bordered viewport's own interior is
    # exactly layout.py's GAME_W x GAME_H -- the canon-cited native content
    # size the bordered viewport wraps with zero inset.
    assert (inner_w, inner_h) == (GAME_W, GAME_H)

    grid = pyte_grid(_content_capture, FULL_ROWS, FULL_COLS)
    pos = find_text(grid, _CONTENT_ROWS[0])
    assert pos is not None, f"expected {_CONTENT_ROWS[0]!r} somewhere on the grid, found nowhere"
    row, col = pos
    assert inner_y <= row < inner_y + inner_h, f"marker row {row} outside interior {inner_y}..{inner_y + inner_h - 1}"
    assert inner_x <= col < inner_x + inner_w, f"marker col {col} outside interior {inner_x}..{inner_x + inner_w - 1}"
    # Top-left anchored: the FIRST fixture row lands on the interior's OWN
    # first row/column, not merely somewhere inside it.
    assert (row, col) == (inner_y, inner_x)


@_PTY_SKIP
def test_multiple_rows_land_in_order_on_consecutive_interior_rows(_content_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    inner_y, inner_x, _inner_w, _inner_h = _interior(center)

    grid = pyte_grid(_content_capture, FULL_ROWS, FULL_COLS)
    for i, expected in enumerate(_CONTENT_ROWS):
        row_text = grid[inner_y + i]
        segment = row_text[inner_x : inner_x + len(expected)]
        assert segment == expected, (
            f"expected fixture row {i} ({expected!r}) at interior row {inner_y + i}, "
            f"got {segment!r} (full row: {row_text!r})"
        )


# ---------------------------------------------------------------------------
# (c) TOP-DROP under height pressure -- the ruled policy
# (``cockpit/viewport.py::compose_viewport_lines``'s own docstring): more
# rows than the interior holds (30 fed, interior holds GAME_H=25) means the
# LAST 25 rows survive, the first 5 are dropped. Waiting on the LAST fed
# row (``OVFL-29``) as the drive's own ready-text makes a wrong (bottom-drop)
# policy fail HONESTLY as a stalled drive, not a mis-assertion.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _overflow_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_paint_overflow")
    return _drive_viewport_paint_pty(tmp_path, fixture="overflow", ready_text=_OVERFLOW_ROWS[-1])


@_PTY_SKIP
def test_overflow_top_drop_keeps_last_rows_sheds_first_rows(_overflow_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    inner_y, inner_x, _inner_w, inner_h = _interior(center)
    assert inner_h == GAME_H
    assert len(_OVERFLOW_ROWS) > inner_h, "fixture must genuinely overflow the interior to prove anything"

    grid = pyte_grid(_overflow_capture, FULL_ROWS, FULL_COLS)
    surviving = _OVERFLOW_ROWS[-inner_h:]  # the policy under test: LAST inner_h rows survive
    dropped = _OVERFLOW_ROWS[:-inner_h]

    # First surviving row (OVFL-05) on the interior's own first row.
    first_row_text = grid[inner_y]
    assert first_row_text[inner_x : inner_x + len(surviving[0])] == surviving[0], (
        f"expected the first SURVIVING row {surviving[0]!r} at the interior's own top row, "
        f"got {first_row_text!r}"
    )
    # Last surviving row (OVFL-29, the drive's own ready-text) on the
    # interior's own last row.
    last_row_text = grid[inner_y + inner_h - 1]
    assert last_row_text[inner_x : inner_x + len(surviving[-1])] == surviving[-1], (
        f"expected the last SURVIVING row {surviving[-1]!r} at the interior's own bottom row, "
        f"got {last_row_text!r}"
    )
    # Every dropped (top) row is absent from the ENTIRE grid, not just the
    # interior -- it must not have been shuffled elsewhere either.
    full_text = "\n".join(grid)
    offenders = [r for r in dropped if r in full_text]
    assert not offenders, f"expected dropped top rows nowhere on screen, found: {offenders!r}"


# ---------------------------------------------------------------------------
# (d) Honest blank preserved: an empty/None WatchFeed payload leaves the
# GAME interior blank -- PWO-051's shell contract must survive live-paint
# wiring, both for a missing event entirely and for a present-but-empty
# screen list.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _empty_none_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_paint_empty_none")
    return _drive_viewport_paint_pty(tmp_path, fixture="empty_none", ready_text=_READY_TEXT)


@pytest.fixture(scope="module")
def _empty_list_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_paint_empty_list")
    return _drive_viewport_paint_pty(tmp_path, fixture="empty_list", ready_text=_READY_TEXT)


@_PTY_SKIP
def test_no_latest_event_renders_honest_blank_interior(_empty_none_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    grid = pyte_grid(_empty_none_capture, FULL_ROWS, FULL_COLS)
    _assert_bordered_interior_blank(grid, center)


@_PTY_SKIP
def test_empty_screen_list_renders_honest_blank_interior(_empty_list_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    grid = pyte_grid(_empty_list_capture, FULL_ROWS, FULL_COLS)
    _assert_bordered_interior_blank(grid, center)


# ---------------------------------------------------------------------------
# (e) Hostile content is contained: a payload row carrying real CSI/OSC
# escape bytes must not corrupt the frame -- the chrome border/title still
# render intact, and the escape does not execute (proven via pyte's own
# structured ``screen.title`` -- OSC 0/2 sets it for real if the sequence
# ever reaches the terminal -- and the resulting grid text, never a regex
# over raw captured bytes).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _hostile_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("viewport_paint_hostile")
    return _drive_viewport_paint_pty(tmp_path, fixture="hostile", ready_text=_HOSTILE_MARKER)


@_PTY_SKIP
def test_hostile_escape_payload_neutralized_and_chrome_intact(_hostile_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    outer, center = regions["outer"], regions["center"]

    screen = pyte_screen(_hostile_capture, FULL_ROWS, FULL_COLS)
    grid = pyte_grid(_hostile_capture, FULL_ROWS, FULL_COLS)

    # The escape sequence did NOT execute: a real OSC 0/2 that reached the
    # terminal would have set pyte's own tracked window title to
    # "evil-title" -- it must not have.
    assert screen.title != "evil-title", (
        f"expected the OSC title-set sequence to be neutralized before reaching the "
        f"terminal, but screen.title == {screen.title!r}"
    )

    # The payload's neutralized ESC became a plain space (alignment
    # preserved), so the bracket/text AROUND it survives as literal,
    # harmless characters -- proving containment without regexing raw
    # escape bytes.
    text = "\n".join(grid)
    assert _HOSTILE_MARKER in text
    assert _HOSTILE_SANITIZED_FRAGMENT in text, (
        f"expected the neutralized escape's literal remnant {_HOSTILE_SANITIZED_FRAGMENT!r} "
        f"in the drawn frame, found none in:\n{text}"
    )

    # Chrome stays intact: the outer frame's own corners and the GAME
    # viewport's own double-border corners are exactly where geometry says.
    _assert_double_border_corners(screen, center)
    ox, oy, ow, oh = outer["x"], outer["y"], outer["w"], outer["h"]
    assert screen.buffer[oy][ox].data == "╔"
    assert screen.buffer[oy][ox + ow - 1].data == "╗"
    assert screen.buffer[oy + oh - 1][ox].data == "╚"
    assert screen.buffer[oy + oh - 1][ox + ow - 1].data == "╝"


# ---------------------------------------------------------------------------
# (f) Esc -> back / q -> quit regression: live viewport paint adds no new
# key handling. Unit-level fake window, mirrors every sibling pty suite's
# own regression leg.
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
    import curses

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
# Bonus (not in the minimum list): ``viewport_provider`` polled exactly
# once per draw -- the contract the dispatch describes ("called once per
# draw()"), mirroring every sibling panel's own poll-guard proof
# (e.g. ``tests/test_cockpit_logsband_pty.py``'s status_provider guard).
# Unit-level, no pty needed.
# ---------------------------------------------------------------------------


class _RecordingSnapshot:
    def __init__(self, latest_event):
        self.latest_event = latest_event


def test_viewport_provider_polled_exactly_once_per_draw(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(FULL_ROWS, FULL_COLS), profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return _RecordingSnapshot({"screen": ["poll-guard-row"]})

    screen.viewport_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one viewport_provider() poll per draw, got {len(calls)}"
    )
