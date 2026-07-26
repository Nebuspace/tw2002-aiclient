"""WO-P3-036 wire — DECISIONS panel stacked below HUD, Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
DECISIONS box the ``screens.py``/``app.py`` wiring produces: the new
``decisions`` region sits below ``HUD`` in the right gutter (unchanged
``right_gutter`` key), both titles visible at the full tier and the
narrowed ``right_gutter`` fold tier (>=138 cols, where only the LEFT
gutter narrows -- the right gutter/DECISIONS width is unaffected), it
renders the composer's two-line honest-empty state with no trace payload,
and a stubbed daemon status with a chosen + gated candidate renders a
``★`` line and a ``⊘`` line on screen. Layer-A coverage for the composer
itself (``compose_decisions_lines``) lives in
``tests/test_cockpit_decisions.py`` (monk-decisions, PWO-036a); this file
only proves the ``PlayShellScreen``/``app.py`` wiring around it -- mirrors
``tests/test_cockpit_goals_pty.py``/``tests/test_cockpit_focus_pty.py``'s
split for GOALS/FOCUS.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned
process (same convention as ``tests/test_cockpit_frame_pty.py``), and
``TW_RUN_DIR`` always points at an isolated per-test tmp directory -- the
real ``status_provider`` (``app._daemon_status_provider``) is free to run
unstubbed against that empty dir (its own ``send_request`` early-returns
``daemon_not_running`` without ever opening a socket) for the no-provider
scenario, and the chosen+gated scenario additionally monkeypatches
``tw2002_aiclient.session.cli.send_request`` inside the bootstrap -- never
``run/twd.sock`` either way.
"""

from __future__ import annotations

import os
import pty
import re
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

# Full tier (both gutters at full width) and the narrowed right_gutter fold
# tier (left gutter narrowed, right gutter/DECISIONS width unaffected --
# HUD_GUTTER_W is a fixed 36 across every has_right_gutter tier) -- the two
# sizes the dispatch calls out ("pty 40×160 and 40×142").
FULL_ROWS, FULL_COLS = 40, 160
NARROW_ROWS, NARROW_COLS = 40, 142

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as tests/test_cockpit_goals_pty.py's / test_cockpit_focus_pty.py's
# _BOOTSTRAP. One opt-in DECISIONS status fixture stubs
# session_cli.send_request's "status" verb with a chosen candidate, an
# unchosen candidate, and one gated candidate.
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

_FIXTURE_DECISIONS = os.environ.get("TW2002_TEST_DECISIONS_FIXTURE") == "1"
if _FIXTURE_DECISIONS:
    from tw2002_aiclient.session import cli as session_cli

    def _fake_send_request(verb, args_payload=None, *, timeout=15.0, run_dir=None):
        if verb == "status":
            return {{
                "ok": True,
                "autopilot_trace": {{
                    "chosen": "run_chain",
                    "candidates": [
                        {{
                            "kind": "run_chain",
                            "ev_cr_per_turn": 12.5,
                            "gated": False,
                            "rationale": "best EV this tick",
                        }},
                        {{
                            "kind": "explore",
                            "ev_cr_per_turn": 3.0,
                            "gated": False,
                            "rationale": "fallback",
                        }},
                        {{
                            "kind": "upgrade",
                            "gated": True,
                            "gate_reason": "no dock",
                        }},
                    ],
                }},
            }}
        return {{"ok": False, "error": "unsupported_verb_in_test_stub"}}

    session_cli.send_request = _fake_send_request

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _drive_decisions_pty(
    tmp_path: Path,
    rows: int,
    cols: int,
    *,
    fixture_decisions: bool = False,
    timeout: float = 12.0,
) -> bytes:
    """Spawn ``app._run`` in a pty sized ``rows``x``cols``: Enter from the
    launcher once its chrome is up, capture the play-shell cockpit frame
    once DECISIONS is visible (letting at least one ~1 Hz refresh tick
    land), then quit. Mirrors
    ``tests/test_cockpit_focus_pty.py::_drive_focus_pty``'s poll-and-decide
    loop.

    ``TW_RUN_DIR`` always points at an isolated tmp dir under ``tmp_path``
    so the real (unstubbed) status_provider path can never reach the
    project's own ``run/twd.sock`` regardless of which fixture is active.
    """
    bootstrap = tmp_path / f"decisions_pty_bootstrap_{rows}x{cols}_{int(fixture_decisions)}.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    isolated_run_dir = tmp_path / "isolated_run"
    isolated_run_dir.mkdir(exist_ok=True)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    env["TW2002_LAUNCHER_DEMO"] = "1"
    env["TW_RUN_DIR"] = str(isolated_run_dir)
    if fixture_decisions:
        env["TW2002_TEST_DECISIONS_FIXTURE"] = "1"
    else:
        env.pop("TW2002_TEST_DECISIONS_FIXTURE", None)
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
                if find_text(grid, "DECISIONS"):
                    # Let at least one ~1 Hz refresh tick land before acting
                    # (proves the timeout-driven redraw doesn't crash/stall).
                    time.sleep(1.3)
                    ready, _, _ = select.select([master_fd], [], [], 0.2)
                    if master_fd in ready:
                        try:
                            chunk = os.read(master_fd, 65536)
                            captured += chunk
                        except OSError:
                            pass
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
        f"pty DECISIONS drive stalled in phase={phase!r} at {rows}x{cols}; last grid:\n"
        + "\n".join(pyte_grid(captured, rows, cols))
    )
    return captured


@pytest.fixture(scope="module")
def _full_tier_no_provider_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("decisions_full_no_provider")
    return _drive_decisions_pty(tmp_path, FULL_ROWS, FULL_COLS)


@pytest.fixture(scope="module")
def _narrow_tier_no_provider_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("decisions_narrow_no_provider")
    return _drive_decisions_pty(tmp_path, NARROW_ROWS, NARROW_COLS)


@pytest.fixture(scope="module")
def _full_tier_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("decisions_full_fixture")
    return _drive_decisions_pty(tmp_path, FULL_ROWS, FULL_COLS, fixture_decisions=True)


@pytest.fixture(scope="module")
def _narrow_tier_fixture_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("decisions_narrow_fixture")
    return _drive_decisions_pty(tmp_path, NARROW_ROWS, NARROW_COLS, fixture_decisions=True)


# ---------------------------------------------------------------------------
# HUD and DECISIONS titles both visible, DECISIONS below HUD, at both tiers.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_full_tier_hud_and_decisions_titles_visible(_full_tier_no_provider_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    assert regions["mode"] == "full"
    hud, decisions = regions["right_gutter"], regions["decisions"]
    assert hud is not None and decisions is not None
    grid = pyte_grid(_full_tier_no_provider_capture, FULL_ROWS, FULL_COLS)

    assert "HUD" in grid[hud["y"]]
    assert "DECISIONS" in grid[decisions["y"]]
    assert hud["y"] < decisions["y"]


@_PTY_SKIP
def test_narrow_right_gutter_tier_hud_and_decisions_titles_visible(_narrow_tier_no_provider_capture):
    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    # >=138 inner cols still carries the right gutter (HUD/DECISIONS) at
    # its full HUD_GUTTER_W -- only the LEFT gutter narrows at this tier.
    assert regions["mode"] == "right_gutter"
    hud, decisions = regions["right_gutter"], regions["decisions"]
    assert hud is not None and decisions is not None
    grid = pyte_grid(_narrow_tier_no_provider_capture, NARROW_ROWS, NARROW_COLS)

    assert "HUD" in grid[hud["y"]]
    assert "DECISIONS" in grid[decisions["y"]]
    assert hud["y"] < decisions["y"]


# ---------------------------------------------------------------------------
# No autopilot_trace payload (real transport, empty isolated run dir; also
# the shape of today's real daemon, which carries no "autopilot_trace" key
# yet) -> the composer's two-line honest-empty state, never blank.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_no_provider_decisions_shows_honest_empty(_full_tier_no_provider_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    decisions = regions["decisions"]
    grid = pyte_grid(_full_tier_no_provider_capture, FULL_ROWS, FULL_COLS)

    content_left = decisions["x"] + 1
    content_right = decisions["x"] + decisions["w"] - 1  # exclusive -- box's own right border
    row0 = grid[decisions["y"] + 1][content_left:content_right].strip()
    row1 = grid[decisions["y"] + 2][content_left:content_right].strip()
    assert row0 == "—", f"expected DECISIONS honest-empty first line, got {row0!r}"
    assert row1 == "Exploring…", f"expected DECISIONS honest-empty second line, got {row1!r}"


# ---------------------------------------------------------------------------
# Stubbed provider: a chosen candidate ("★"), an unchosen candidate ("·"),
# and a gated candidate ("⊘") render on screen, at both tiers.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_full_tier_stubbed_provider_shows_chosen_and_gated_lines(_full_tier_fixture_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    decisions = regions["decisions"]
    grid = pyte_grid(_full_tier_fixture_capture, FULL_ROWS, FULL_COLS)
    decisions_text = "\n".join(
        grid[decisions["y"] + 1 : decisions["y"] + decisions["h"] - 1]
    )

    assert "★" in decisions_text
    assert "Trade chain" in decisions_text
    assert "⊘" in decisions_text
    assert "Upgrade" in decisions_text


@_PTY_SKIP
def test_narrow_tier_stubbed_provider_shows_chosen_and_gated_lines(_narrow_tier_fixture_capture):
    regions = frame_layout(NARROW_ROWS, NARROW_COLS)
    decisions = regions["decisions"]
    grid = pyte_grid(_narrow_tier_fixture_capture, NARROW_ROWS, NARROW_COLS)
    decisions_text = "\n".join(
        grid[decisions["y"] + 1 : decisions["y"] + decisions["h"] - 1]
    )

    assert "★" in decisions_text
    assert "Trade chain" in decisions_text
    assert "⊘" in decisions_text
    assert "Upgrade" in decisions_text


# ---------------------------------------------------------------------------
# D5 static check: DECISIONS carries no AI-drives badge, and (mirroring
# focus.py's own check) no send/socket-write call shape -- display-only.
# ---------------------------------------------------------------------------


def test_decisions_composer_and_wire_have_no_ai_pilot_badge_or_send_surface():
    """D5 (PREP hard-gate): no ``ai_pilot``/``AI-PILOT`` badge text anywhere
    in the DECISIONS composer or its ``screens.py`` wire -- DECISIONS is
    read-only reasoning display, never a live-drive indicator. Also asserts
    the composer itself has no send/socket-write call shape, same static
    check ``tests/test_cockpit_focus_pty.py`` runs on ``focus.py``."""
    decisions_src = (PROJECT_ROOT / "tw2002_aiclient" / "cockpit" / "decisions.py").read_text(
        encoding="utf-8"
    )
    screens_src = (PROJECT_ROOT / "tw2002_aiclient" / "screens.py").read_text(encoding="utf-8")

    badge_re = re.compile(r"ai[_-]pilot", re.IGNORECASE)
    assert not badge_re.search(decisions_src), "ai_pilot badge text found in decisions.py"
    assert not badge_re.search(screens_src), "ai_pilot badge text found in screens.py"

    call_shaped = re.compile(r"\b(?:socket|send_keys|os\.write)\s*\(")
    hits = call_shaped.findall(decisions_src)
    assert hits == [], f"unexpected send/socket-write call shape(s) in decisions.py: {hits}"


def test_play_shell_screen_handle_key_unchanged_esc_and_q_only(monkeypatch):
    """DECISIONS wiring must not add any new key handling -- Esc still
    returns ``back``, ``q``/``Q`` still return ``quit``, and every other
    key still returns ``None``. Pure unit check, no pty needed. Mirrors
    ``tests/test_cockpit_focus_pty.py``'s equivalent check."""
    import curses

    from tw2002_aiclient import screens as screens_mod

    # _init_colors() calls curses.has_colors(), which requires a live
    # initscr() outside a real curses session -- stub it False (monochrome
    # path) same as the goals/focus pty suites' equivalent unit tests.
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    class _NullWin:
        def getmaxyx(self):
            return (40, 160)

        def erase(self):
            return None

        def addstr(self, *a, **k):
            return None

        def refresh(self):
            return None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(_NullWin(), profile)

    assert screen.handle_key(27) == "back"
    assert screen.handle_key(ord("q")) == "quit"
    assert screen.handle_key(ord("Q")) == "quit"
    for key in (curses.KEY_UP, curses.KEY_DOWN, ord("1"), ord("d"), ord(" ")):
        assert screen.handle_key(key) is None
