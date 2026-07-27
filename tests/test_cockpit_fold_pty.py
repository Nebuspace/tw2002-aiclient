"""WO-P3-039 wire -- responsive fold, Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
``decisions`` box the ``screens.py``/``app.py`` wiring produces once the
narrow-right fold tier is reached: below ``layout.LEFT_GUTTER_MIN_COLS``
(138) the left gutter is entirely absent (``regions["goals"] is None``)
while the DECISIONS host still survives, and GOALS+FOCUS content relocates
INTO that pane (canon `trainer-cockpit.md` "Responsive fold") via
``cockpit.fold.compose_folded_decisions_lines`` in place of
``cockpit.decisions.compose_decisions_lines`` for that one draw call. At
>=138 cols nothing changes -- the left gutter survives and DECISIONS keeps
showing only its own trace content. Layer-A coverage for the composer
itself lives in the sibling composer WO's own test file; this file only
proves the ``PlayShellScreen``/``app.py`` wiring around it -- mirrors
``tests/test_cockpit_decisions_pty.py``'s split for DECISIONS and
``tests/test_cockpit_liveness_pty.py``'s split for the control strip.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned process
(same convention as every sibling cockpit-panel pty suite), and
``TW_RUN_DIR`` always points at an isolated per-test tmp directory -- the
real ``status_provider`` (``app._daemon_status_provider``) is free to run
unstubbed against that empty dir (its own ``send_request`` early-returns
``daemon_not_running`` without ever opening a socket) for the no-fixture
scenario, and the ``data``/``escape`` fixtures additionally monkeypatch
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
    set_winsize,
    terminate_session_group,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# The two sizes the dispatch calls out: 40x122 is a genuine narrow-right
# fold tier (122-2=120 inner cols -- inside [RIGHT_GUTTER_MIN_COLS=118,
# LEFT_GUTTER_MIN_COLS=138), so `goals` is None and `decisions` survives);
# 40x142 is the same "right_gutter" fold *mode* but wide enough
# (142-2=140 inner cols >= 138) that the left gutter (and `goals`) still
# fits -- no fold. Both share HUD_GUTTER_W=36 for the right gutter/
# DECISIONS box itself, so DECISIONS' own width and height are identical
# at both sizes; only whether `goals` is None differs.
NARROW_ROWS, NARROW_COLS = 40, 122
WIDE_ROWS, WIDE_COLS = 40, 142

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as every sibling cockpit-panel pty suite's own bootstrap. One
# opt-in fold-content fixture stubs session_cli.send_request's "status" verb.
#
# "data" carries GOALS-shaped top-level fields (credits/turns_left), a
# one-candidate ``autopilot_trace`` (kind "explore" -- deliberately NOT
# "run_chain", so its "Explore" label can never be mistaken on screen for
# FOCUS's own "Trade chain" text -- see the real-geometry note in
# ``test_narrow_tier_shows_decisions_title_and_folded_goals_focus_content``
# below), and a one-candidate FOCUS payload (kind "run_chain" -> "Trade
# chain"). "escape" carries only credits + a hostile GOALS string field
# (``hold_price_label``) -- no trace/focus, kept minimal since that test
# only needs GOALS to render at all -- to prove the folded path still runs
# through the draw layer's own control-char sanitize choke point, mirroring
# tests/test_cockpit_hud_pty.py's own "escape" fixture shape applied to a
# GOALS value instead of a HUD one.
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

_FOLD_FIXTURE = os.environ.get("TW2002_TEST_FOLD_FIXTURE", "")
if _FOLD_FIXTURE:
    from tw2002_aiclient.session import cli as session_cli

    if _FOLD_FIXTURE == "data":
        def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
            if verb == "status":
                return {{
                    "ok": True,
                    "credits": 54321,
                    "turns_left": 120,
                    "autopilot_trace": {{
                        "chosen": "explore",
                        "candidates": [
                            {{
                                "kind": "explore",
                                "ev_cr_per_turn": 1.0,
                                "gated": False,
                                "rationale": "scouting",
                            }},
                        ],
                    }},
                    "focus": {{
                        "candidates": [
                            {{"kind": "run_chain", "ev_per_turn": 12.5, "gated": False}},
                            {{"kind": "upgrade", "ev_per_turn": 5.0, "gated": False}},
                        ],
                    }},
                }}
            return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}

        session_cli.send_request = _fake_send_request
    elif _FOLD_FIXTURE == "escape":
        def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
            if verb == "status":
                return {{
                    "ok": True,
                    "credits": 54321,
                    "hold_price_label": "\x1b[2Jinjected",
                }}
            return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}

        session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _settle(master_fd: int, captured: bytes, seconds: float) -> bytes:
    """Keep draining ``master_fd`` for ``seconds`` of wall time, accumulating
    onto ``captured`` -- a single post-sleep ``read()`` isn't reliable here
    (``PlayShellScreen.draw()``'s one ``refresh()`` call still spans
    multiple OS-level pty read chunks for a full frame), same lesson and
    same helper shape as ``tests/test_cockpit_liveness_pty.py::_settle``.
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


def _drive_fold_pty(
    tmp_path: Path,
    rows: int,
    cols: int,
    *,
    ready_text: str,
    fixture: str = "",
    timeout: float = 12.0,
) -> bytes:
    """Spawn ``app._run`` in a pty sized ``rows``x``cols``: Enter from the
    launcher once its chrome is up, capture the play-shell cockpit frame
    once ``ready_text`` is visible ANYWHERE on screen (letting at least one
    ~1 Hz refresh tick fully settle after that), then quit. Mirrors
    ``tests/test_cockpit_decisions_pty.py::_drive_decisions_pty``'s
    poll-and-decide loop, with the fuller ``_settle`` drain
    ``tests/test_cockpit_liveness_pty.py`` uses instead of a single
    post-sleep read.

    ``ready_text`` must be the actual fixture-specific CONTENT this drive
    is looking for (e.g. the folded Credits value ``"54,321"`` for the
    ``"data"`` fixture, the neutralized escape payload ``"2Jinjected"`` for
    ``"escape"``, ``"Exploring…"`` for the honest-empty no-fixture case) --
    never the bare ``"DECISIONS"`` box title, which is drawn on the FIRST
    frame regardless of whether the status_provider's data has reached the
    composer yet. A one-shot flake was observed (sibling composer worker,
    full-suite run) where the captured grid showed the trace section's
    empty marker and no FOCUS label despite the ``"data"`` fixture being
    active -- reproduced re-runs stayed green, the signature of the capture
    window closing on an early, not-yet-data-bearing frame rather than a
    real bug. Waiting on the bare box title and then a FIXED-time settle
    (the previous shape here) is exactly the same hazard family as the
    WO-P3-038 lesson that produced ``_settle`` in the first place -- a
    fixed sleep can still snapshot mid-flush under CPU contention; the fix
    here is the same *class* of fix one level up the chain: make the
    capture CONDITION-driven on the actual awaited content, with the
    overall ``timeout`` staying as the only time-based backstop (the
    ``_settle`` drain below still runs, unchanged, AFTER the condition is
    met, since frame-completeness -- multiple pty read chunks per
    ``refresh()`` -- is still a separate, real hazard from *which* frame
    was captured).

    ``TW_RUN_DIR`` always points at an isolated tmp dir under ``tmp_path``
    so the real (unstubbed) status_provider path can never reach the
    project's own ``run/twd.sock`` regardless of which fixture is active.
    """
    bootstrap = tmp_path / f"fold_pty_bootstrap_{rows}x{cols}_{fixture or 'none'}.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if fixture:
        env["TW2002_TEST_FOLD_FIXTURE"] = fixture
    else:
        env.pop("TW2002_TEST_FOLD_FIXTURE", None)
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
        terminate_session_group(proc)
        try:
            os.close(master_fd)
        except OSError:
            pass

    assert phase == "done", (
        f"pty fold drive stalled in phase={phase!r} at {rows}x{cols}; last grid:\n"
        + "\n".join(pyte_grid(captured, rows, cols))
    )
    return captured


@pytest.fixture(scope="module")
def _narrow_no_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("fold_narrow_no_fixture")
    # No fixture -> status_provider resolves to None -> the fold composer's
    # all-empty collapse, ["—", "Exploring…"] -- wait for its own second
    # line, the genuine content this drive needs on screen.
    return _drive_fold_pty(tmp_path, NARROW_ROWS, NARROW_COLS, ready_text="Exploring…")


@pytest.fixture(scope="module")
def _narrow_data_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("fold_narrow_data")
    # The folded Credits value -- only present once the "data" fixture's
    # real status has actually reached the composer (not just once the
    # DECISIONS box title itself is drawn, which happens on frame 1
    # regardless of data).
    return _drive_fold_pty(tmp_path, NARROW_ROWS, NARROW_COLS, ready_text="54,321", fixture="data")


@pytest.fixture(scope="module")
def _wide_data_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("fold_wide_data")
    return _drive_fold_pty(tmp_path, WIDE_ROWS, WIDE_COLS, ready_text="54,321", fixture="data")


@pytest.fixture(scope="module")
def _narrow_escape_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("fold_narrow_escape")
    # The neutralized escape payload itself -- proves the hostile frame
    # (not just some earlier frame) is what got captured.
    return _drive_fold_pty(tmp_path, NARROW_ROWS, NARROW_COLS, ready_text="2Jinjected", fixture="escape")


# ---------------------------------------------------------------------------
# Narrow-right tier (40x122, fold ACTIVE): GOALS+FOCUS content relocates
# into the DECISIONS box.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_narrow_tier_fold_active_goals_absent(_narrow_data_fixture_capture):
    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    assert regions["mode"] == "right_gutter"
    assert regions["goals"] is None, "40x122 must be a genuine goals-absent fold tier"
    assert regions["decisions"] is not None, "DECISIONS host must survive at this tier"


@_PTY_SKIP
def test_narrow_tier_shows_decisions_title_and_folded_goals_focus_content(
    _narrow_data_fixture_capture,
):
    """Real-geometry finding (verified against the live composers before
    writing this assertion, not assumed): at the fold-active tier the
    DECISIONS box's content budget plateaus at a hard ``inner_h == 13``
    ceiling -- ``layout.py``'s ``VIEWPORT_H``/``HUD_BOX_MIN_H`` constants
    cap ``decisions["h"]`` at 15 (content 13) -- but only from **34
    terminal rows up** (``VIEWPORT_H`` grew 26->27 when the GAME viewport
    was widened to the daemon's true native 80x25 grid, which pushed this
    plateau's own onset up by one row too, from 33 to 34); this test's own
    40-row fixture (``NARROW_ROWS``) sits safely on that plateau, so the
    assertions below are unaffected. Below 34 rows the box actually SHRINKS
    with height (an adversarial-pass sweep, corrected here after an earlier
    draft of this docstring overclaimed "at ANY terminal height" without
    checking below 40 rows): at a fold-active column, ``decisions["h"]``
    climbs 1 row per terminal row from ``lines=21`` (h=2, title-only --
    ``draw_box``'s own ``h < 2`` guard means ``lines=20`` -- the official
    too-small floor -- drops the box, border and all) up through
    ``lines=33`` (h=14, content 12) before plateauing to h=15/content=13 at
    ``lines=34``. This is ``layout.py``'s pre-existing PWO-036 stacked-gutter
    height split (HUD claims its floor first, DECISIONS gets whatever
    remains) -- unrelated to this WO's own fold logic, column-independent,
    and present at unfolded ``>=138``-col tiers too. It is NOT a WO-P3-039
    regression (before this WO, GOALS/FOCUS simply didn't exist below 138
    cols at any height, so there was nothing to compare against; the fold
    strictly improves every reachable height ``>=22``) -- but it is
    disclosed to the hub as a DECISIONS-height-policy follow-on (the
    low-height floor and the 13-row ceiling below are the same design knob,
    both ends of it) rather than patched in this wire-only WO.

    GOALS alone is a fixed, non-negotiable 10-line footprint (its own
    "GOALS" label + the canon-mandated 9 rows that "never vanish",
    ``goals.py``), and the trace section above it is never fewer than 1
    line once it carries a real candidate -- 1 + 10 == 11, leaving exactly
    two more rows at the 13-row plateau: the "FOCUS" label claims line 11,
    and FOCUS's own rank-led first candidate (kind "run_chain" -> "Trade
    chain") now fits at line 12 -- both visible on screen. Growing the
    plateau by one row (26->27) means a single-candidate FOCUS fixture no
    longer overflows the box at all, so this fixture carries a SECOND FOCUS
    candidate (kind "upgrade" -> "Upgrade") purely to keep exercising real
    shedding: that second candidate lands at line 13, one past the ceiling
    -- REAL, DOCUMENTED, INTENTIONAL bottom-first shedding (fold.py's own
    module docstring: "FOCUS (last) sheds before GOALS (middle) before the
    trace (first)"), not a wiring bug. This test therefore proves what a
    real operator terminal actually shows (GOALS' label + real content,
    FOCUS's own label AND its first-ranked line) via the pty capture, and
    separately proves the WIRE still threads the full status+width through
    correctly (FOCUS's second candidate line genuinely present in the
    composed output, just shed by height) via a direct call to the same
    composer with the same status/width below -- the same two-layer split
    ``tests/test_cockpit_hud_pty.py`` uses between "what renders" and "what
    pyte can prove" for its own A_DIM case.
    """
    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    decisions = regions["decisions"]
    grid = pyte_grid(_narrow_data_fixture_capture, NARROW_ROWS, NARROW_COLS)

    assert "DECISIONS" in grid[decisions["y"]], "DECISIONS box title must stay unchanged when folded"

    decisions_text = "\n".join(grid[decisions["y"] + 1 : decisions["y"] + decisions["h"] - 1])

    assert "GOALS" in decisions_text, f"expected a GOALS label row folded into DECISIONS, got:\n{decisions_text}"
    assert "FOCUS" in decisions_text, f"expected the FOCUS label row folded into DECISIONS, got:\n{decisions_text}"
    # Real GOALS rows (Turns, Credits -- formatted with the composer's own
    # thousands separator) -- proves actual panel CONTENT relocated, not
    # just the section label.
    assert "120" in decisions_text, f"expected the folded Turns value, got:\n{decisions_text}"
    assert "54,321" in decisions_text, f"expected the folded Credits value, got:\n{decisions_text}"
    # FOCUS's first-ranked candidate now fits inside the (grown) 13-row
    # plateau -- genuinely visible on screen, not shed.
    assert "Trade chain" in decisions_text, (
        f"expected FOCUS's first-ranked candidate line on screen, got:\n{decisions_text}"
    )
    # The fixture's SECOND candidate is the one this test relies on being
    # shed -- if it ever starts appearing on screen too, the plateau grew
    # again and this fixture (and the docstring above) need another look.
    assert "Upgrade" not in decisions_text, (
        f"expected FOCUS's second candidate to be shed past the plateau, got:\n{decisions_text}"
    )

    # Companion proof (not pty-visible, see docstring above): the same
    # status dict and the same box width the wire actually used really did
    # produce a rank-led FOCUS line -- it is shed by real box height, not
    # missing from the composed content.
    from tw2002_aiclient.cockpit import fold as cockpit_fold

    width = decisions["w"] - 2
    composed = cockpit_fold.compose_folded_decisions_lines(
        {
            "ok": True,
            "credits": 54321,
            "turns_left": 120,
            "autopilot_trace": {
                "chosen": "explore",
                "candidates": [
                    {"kind": "explore", "ev_cr_per_turn": 1.0, "gated": False, "rationale": "scouting"},
                ],
            },
            "focus": {
                "candidates": [
                    {"kind": "run_chain", "ev_per_turn": 12.5, "gated": False},
                    {"kind": "upgrade", "ev_per_turn": 5.0, "gated": False},
                ],
            },
        },
        width=width,
    )
    assert any("Trade chain" in line for line in composed), (
        f"expected a rank-led FOCUS line in the fold composer's own output, got: {composed}"
    )
    assert any("Upgrade" in line for line in composed), (
        f"expected the second rank-led FOCUS line in the fold composer's own output, got: {composed}"
    )
    inner_h = decisions["h"] - 2
    assert len(composed) > inner_h, (
        "expected this fixture to genuinely overflow the box -- if it no longer does, the "
        "real-geometry finding above may be stale and this test's on-screen assertions "
        "should be revisited"
    )


# ---------------------------------------------------------------------------
# Wide-right tier (40x142, NO fold): GOALS content stays in the left
# gutter; DECISIONS never carries the GOALS/FOCUS label rows.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_wide_tier_no_fold_goals_present_in_left_gutter(_wide_data_fixture_capture):
    regions = frame_layout(WIDE_ROWS, WIDE_COLS)
    assert regions["mode"] == "right_gutter"
    goals = regions["goals"]
    assert goals is not None, "40x142 must keep the left GOALS gutter (>=138 inner cols)"
    grid = pyte_grid(_wide_data_fixture_capture, WIDE_ROWS, WIDE_COLS)

    assert "GOALS" in grid[goals["y"]], "GOALS box title must render in its own left-gutter box"
    goals_text = "\n".join(grid[goals["y"] + 1 : goals["y"] + goals["h"] - 1])
    assert "54,321" in goals_text, f"expected the real Credits value in the unfolded GOALS box, got:\n{goals_text}"


@_PTY_SKIP
def test_wide_tier_decisions_box_never_contains_folded_labels(_wide_data_fixture_capture):
    regions = frame_layout(WIDE_ROWS, WIDE_COLS)
    decisions = regions["decisions"]
    assert decisions is not None
    grid = pyte_grid(_wide_data_fixture_capture, WIDE_ROWS, WIDE_COLS)

    assert "DECISIONS" in grid[decisions["y"]]
    decisions_text = "\n".join(grid[decisions["y"] + 1 : decisions["y"] + decisions["h"] - 1])

    assert "GOALS" not in decisions_text, f"unfolded DECISIONS must never carry a GOALS label row, got:\n{decisions_text}"
    assert "FOCUS" not in decisions_text, f"unfolded DECISIONS must never carry a FOCUS label row, got:\n{decisions_text}"
    assert "Trade chain" not in decisions_text, (
        f"unfolded DECISIONS must never carry FOCUS candidate content, got:\n{decisions_text}"
    )


# ---------------------------------------------------------------------------
# All-empty fold (40x122, no fixture -- no daemon at all): the same
# two-line honest-empty state as unfolded DECISIONS, no label spam.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_narrow_tier_all_empty_fold_shows_honest_empty_no_labels(_narrow_no_fixture_capture):
    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    assert regions["goals"] is None
    decisions = regions["decisions"]
    assert decisions is not None
    grid = pyte_grid(_narrow_no_fixture_capture, NARROW_ROWS, NARROW_COLS)

    content_left = decisions["x"] + 1
    content_right = decisions["x"] + decisions["w"] - 1  # exclusive -- box's own right border
    row0 = grid[decisions["y"] + 1][content_left:content_right].strip()
    row1 = grid[decisions["y"] + 2][content_left:content_right].strip()
    assert row0 == "—", f"expected the folded all-empty first line, got {row0!r}"
    assert row1 == "Exploring…", f"expected the folded all-empty second line, got {row1!r}"

    decisions_text = "\n".join(grid[decisions["y"] + 1 : decisions["y"] + decisions["h"] - 1])
    assert "GOALS" not in decisions_text, "no label spam when nothing was actually folded in"
    assert "FOCUS" not in decisions_text, "no label spam when nothing was actually folded in"


# ---------------------------------------------------------------------------
# Hostile: an ESC-sequence string inside a folded GOALS value renders
# inert -- the draw layer's control-char sanitize choke point holds on the
# folded path too, mirroring
# tests/test_cockpit_hud_pty.py::test_full_tier_escape_sequence_value_neutralized_not_interpreted.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_narrow_tier_escape_sequence_in_folded_goals_value_renders_inert(
    _narrow_escape_fixture_capture,
):
    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    outer = regions["outer"]
    decisions = regions["decisions"]
    assert decisions is not None
    grid = pyte_grid(_narrow_escape_fixture_capture, NARROW_ROWS, NARROW_COLS)
    text = "\n".join(grid)

    # The neutralized ESC becomes a plain space -- "2Jinjected" survives as
    # literal, harmless text. Had the real escape been interpreted, this
    # substring would never appear (consumed as a control sequence instead
    # of printed), and the chrome checked below would be wiped.
    assert "2Jinjected" in text, f"expected the neutralized escape sequence to render as literal text, got:\n{text}"
    assert "PLAY SHELL" in grid[outer["y"]], "outer frame chrome missing -- screen may have cleared"
    decisions_text = "\n".join(grid[decisions["y"] : decisions["y"] + decisions["h"]])
    assert "DECISIONS" in decisions_text, "DECISIONS box title missing -- screen may have cleared"


# ---------------------------------------------------------------------------
# One-poll instrumentation at the narrow (fold-active) tier -- a real,
# structural guarantee (the fold-active condition is a strict subset of the
# existing `decisions is not None` poll-guard term, see screens.py's own
# comment), pinned here as a unit-level test mirroring
# tests/test_cockpit_liveness_pty.py's own poll-guard tests.
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


def test_poll_guard_fires_exactly_once_at_narrow_fold_active_tier(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    assert regions["goals"] is None
    assert regions["decisions"] is not None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _NullWin(NARROW_ROWS, NARROW_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"credits": 1}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one status_provider poll at the fold-active narrow tier, got {len(calls)}"
    )


# ---------------------------------------------------------------------------
# handle_key unchanged -- the fold wiring adds no new key handling.
# ---------------------------------------------------------------------------


def test_play_shell_screen_handle_key_unchanged_esc_and_q_only(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(NARROW_ROWS, NARROW_COLS), profile)

    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("Q")) == "quit"
    # `ord(" ")` (Space) dropped from this list -- WO-AUTOLOOP-RELAUNCH-COCKPIT
    # legitimately binds it to the pause intent; this pin is only about
    # THIS module's own wiring not adding new key handling.
    for key in (curses.KEY_UP, curses.KEY_DOWN, ord("1"), ord("d")):
        assert screen.handle_key(key) is None
