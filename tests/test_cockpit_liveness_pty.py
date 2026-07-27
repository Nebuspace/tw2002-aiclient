"""WO-P3-038 wire -- control-strip liveness cluster, Layer-B.

Real-curses pty + pyte replay (``tests.pty_helpers``) proves the *drawn*
``control_strip`` row the ``screens.py``/``app.py`` wiring produces: the
liveness cluster (heartbeat/spinner/``→ TX``) is visible at the full tier
and at the narrowest gutter-less ``minimal`` fold tier, the heartbeat glyph
genuinely changes cell content across a controlled-clock two-capture proof,
the idle ``→ -`` TX readout renders with no wire bridge in place, and the
ASCII-twin run swaps the heartbeat/spinner glyphs while ``→`` (NO-SWAP)
survives unchanged. Layer-A coverage for the composer itself
(``compose_liveness_cluster``) lives in ``tests/test_cockpit_liveness.py``
(the sibling composer WO); this file only proves the ``PlayShellScreen``/
``app.py`` wiring around it -- mirrors ``tests/test_cockpit_hud_pty.py``'s
split for HUD.

Isolation: ``adapters.ensure_session`` is stubbed inside the spawned process
(same convention as every sibling cockpit-panel pty suite), and
``TW_RUN_DIR`` always points at an isolated per-test tmp directory -- the
real (unstubbed) ``status_provider`` (``app._daemon_status_provider``) is
free to run against that empty dir (its own ``send_request`` early-returns
``daemon_not_running`` without ever opening a socket) -- never
``run/twd.sock``.

Controlled clock: ``PlayShellScreen``'s own clock seam (``now_fn``, WO-P3-038)
has no wire from ``app.py`` (deliberately -- the dispatch forbids touching
``app.py``), so this file's bootstrap instead monkeypatches
``tw2002_aiclient.screens.time.monotonic`` inside the spawned subprocess to
read a float from a small tmp file (``TW2002_TEST_CLOCK_FILE``) that the
OUTER test process rewrites between captures. This keeps the two heartbeat
PHASE VALUES themselves fully deterministic (``0.0`` then ``1.2`` --
computed offsets, not measured wall-clock deltas); the ``time.sleep(1.3)``
calls in the driver below only let the subprocess's own real ~1 Hz
``stdscr.timeout(1000)`` redraw loop land a tick after each clock-file
write, the same "let a refresh tick land" wait every sibling pty suite
already does (e.g. ``tests/test_cockpit_hud_pty.py``'s own
``time.sleep(1.3)``) -- never a sleep used to *produce* the phase value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.pty_ui


import curses

from tw2002_aiclient.cockpit import liveness as cockpit_liveness
from tw2002_aiclient.cockpit.layout import frame_layout

from .pty_helpers import (
    drive_play_shell_pty,
    find_text,
    pty_curses_supported,
    pyte_grid,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HANDLE = "Alpha"
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

# Full tier (both gutters, right_gutter/HUD present) and the gutter-less
# `minimal` fold tier (no GOALS/FOCUS/HUD/DECISIONS at all -- the tier this
# WO's poll-guard extension is genuinely LIVE at, not defensive) -- the
# `minimal_rows, minimal_cols = 25, 100` pair mirrors
# ``tests/test_cockpit_hud_pty.py::test_poll_guard_zero_calls_at_minimal_tier_with_no_status_consumer``'s
# own real-tier constants for consistency across the suite.
FULL_ROWS, FULL_COLS = 40, 160
MINIMAL_ROWS, MINIMAL_COLS = 25, 100

_TX_IDLE = "→ -"

# Bootstrap: demo launcher rows + stubbed ensure (no daemon / no twd.sock),
# same shape as every sibling cockpit-panel pty suite's own bootstrap. The
# clock-file monkeypatch is opt-in (only wired when
# ``TW2002_TEST_CLOCK_FILE`` is set) so a driver run that doesn't need the
# controlled-clock proof still exercises the REAL ``time.monotonic``.
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

_CLOCK_FILE = os.environ.get("TW2002_TEST_CLOCK_FILE", "")
if _CLOCK_FILE:
    from pathlib import Path

    from tw2002_aiclient import screens as screens_mod

    def _fake_monotonic():
        try:
            return float(Path(_CLOCK_FILE).read_text().strip())
        except Exception:
            return 0.0

    screens_mod.time.monotonic = _fake_monotonic

import curses
from tw2002_aiclient.app import _run

curses.wrapper(_run)
"""


def _drive_liveness_pty(
    tmp_path: Path,
    rows: int,
    cols: int,
    *,
    ascii_mode: bool = False,
    two_capture: bool = False,
    timeout: float = 14.0,
) -> tuple[bytes, bytes | None]:
    """Spawn ``app._run`` in a pty sized ``rows``x``cols`` via shared
    ``drive_play_shell_pty`` (WO-PTY-DRIVE-HOIST)."""
    bootstrap = tmp_path / f"liveness_pty_bootstrap_{rows}x{cols}.py"
    bootstrap.write_text(_BOOTSTRAP.format(project_root=str(PROJECT_ROOT)), encoding="utf-8")
    clock_file = tmp_path / "clock.txt"
    clock_file.write_text("0.0", encoding="utf-8")

    def after_first_frame(_master_fd: int, captured: bytes) -> tuple[bytes, bool]:
        if two_capture:
            clock_file.write_text("1.2", encoding="utf-8")
            return captured, True
        return captured, False

    env_extra = {"TW2002_TEST_CLOCK_FILE": str(clock_file)}
    pops = [
        "TW2002_HANDOFF_SMOKE",
        "TW2002_LAUNCHER_SMOKE",
        "TW2002_BANK_SMOKE",
    ]
    if ascii_mode:
        env_extra["TW2002_ASCII"] = "1"
    else:
        pops = ["TW2002_ASCII", *pops]

    return drive_play_shell_pty(
        bootstrap,
        project_root=PROJECT_ROOT,
        rows=rows,
        cols=cols,
        handle=HANDLE,
        timeout=timeout,
        env_extra=env_extra,
        env_pops=pops,
        after_first_frame=after_first_frame,
    )


@pytest.fixture(scope="module")
def _full_tier_two_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("liveness_full_two_capture")
    return _drive_liveness_pty(tmp_path, FULL_ROWS, FULL_COLS, two_capture=True)


@pytest.fixture(scope="module")
def _full_tier_ascii_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("liveness_full_ascii")
    capture1, _ = _drive_liveness_pty(tmp_path, FULL_ROWS, FULL_COLS, ascii_mode=True)
    return capture1


@pytest.fixture(scope="module")
def _minimal_tier_capture(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("liveness_minimal")
    capture1, _ = _drive_liveness_pty(tmp_path, MINIMAL_ROWS, MINIMAL_COLS)
    return capture1


def _expected_heartbeat_col(control_strip: dict, now_val: float, *, unicode_ok: bool = True) -> int:
    """The heartbeat glyph's cell column: the composed cluster is
    right-justified into the row (``screens.py``'s own ``.rjust(cs_w)``),
    and the heartbeat glyph is always the cluster's own first character --
    so its column is the row's right edge minus the cluster's own length.
    Computed from the real composer (with the same ``status=None`` the app
    itself resolves to here -- no daemon/wire bridge in this isolated run)
    rather than a hand-counted magic offset.
    """
    cluster = cockpit_liveness.compose_liveness_cluster(
        None, now=now_val, width=control_strip["w"], unicode_ok=unicode_ok
    )
    return control_strip["x"] + control_strip["w"] - len(cluster)


# ---------------------------------------------------------------------------
# Controlled-clock two-capture proof: the heartbeat glyph genuinely changes
# on screen, not just in the pure composer (Layer-A already covers that).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_full_tier_heartbeat_glyph_changes_between_controlled_clock_captures(
    _full_tier_two_capture,
):
    capture1, capture2 = _full_tier_two_capture
    assert capture2 is not None, "two_capture drive did not produce a second capture"

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    control_strip = regions["control_strip"]
    assert control_strip is not None

    col1 = _expected_heartbeat_col(control_strip, 0.0)
    col2 = _expected_heartbeat_col(control_strip, 1.2)
    assert col1 == col2, (
        "idle-TX + calm-spinner cluster length must be identical at both clock "
        "values -- only the heartbeat glyph itself should differ"
    )

    row = control_strip["y"]
    grid1 = pyte_grid(capture1, FULL_ROWS, FULL_COLS)
    grid2 = pyte_grid(capture2, FULL_ROWS, FULL_COLS)
    cell1 = grid1[row][col1]
    cell2 = grid2[row][col2]

    assert cell1 == "●", f"expected phase-0 heartbeat (now=0.0) at capture 1, got {cell1!r}"
    assert cell2 == "○", f"expected phase-1 heartbeat (now=1.2) at capture 2, got {cell2!r}"
    assert cell1 != cell2, "heartbeat glyph did not change at the same cell between captures"


# ---------------------------------------------------------------------------
# Idle TX + cluster presence at the full tier and the gutter-less `minimal`
# boundary tier (this WO's chosen present/absent behavior: height-driven,
# independent of the column's fold mode).
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_full_tier_idle_tx_readout_and_cluster_visible(_full_tier_two_capture):
    capture1, _ = _full_tier_two_capture
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    control_strip = regions["control_strip"]
    assert control_strip is not None
    grid = pyte_grid(capture1, FULL_ROWS, FULL_COLS)
    row_text = grid[control_strip["y"]]

    assert _TX_IDLE in row_text, f"expected idle TX readout in control strip row, got {row_text!r}"
    assert "●" in row_text or "○" in row_text, (
        f"expected the heartbeat glyph in the control strip row, got {row_text!r}"
    )


@_PTY_SKIP
def test_minimal_tier_cluster_present_despite_no_side_gutters(_minimal_tier_capture):
    """CONTROL_STRIP's presence is decided by height alone, independent of
    the column's fold ``mode`` (layout.py's own deliberate WO-P3-038
    choice) -- proven here at the real gutter-less ``minimal`` tier
    (GOALS/FOCUS/HUD/DECISIONS all absent), the chosen boundary behavior
    this WO pins."""
    regions = frame_layout(MINIMAL_ROWS, MINIMAL_COLS)
    assert regions["mode"] == "minimal"
    assert regions["goals"] is None
    assert regions["right_gutter"] is None
    control_strip = regions["control_strip"]
    assert control_strip is not None

    grid = pyte_grid(_minimal_tier_capture, MINIMAL_ROWS, MINIMAL_COLS)
    row_text = grid[control_strip["y"]]
    assert _TX_IDLE in row_text, f"expected idle TX readout at the minimal tier, got {row_text!r}"
    assert "●" in row_text or "○" in row_text, (
        f"expected the heartbeat glyph at the minimal tier, got {row_text!r}"
    )


# ---------------------------------------------------------------------------
# ASCII-twin run: heartbeat/spinner swap to their ASCII glyphs; → (NO-SWAP)
# survives unchanged.
# ---------------------------------------------------------------------------


@_PTY_SKIP
def test_full_tier_ascii_mode_swaps_heartbeat_but_tx_arrow_survives(_full_tier_ascii_capture):
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    control_strip = regions["control_strip"]
    assert control_strip is not None
    grid = pyte_grid(_full_tier_ascii_capture, FULL_ROWS, FULL_COLS)
    row_text = grid[control_strip["y"]]

    assert "●" not in row_text and "○" not in row_text, (
        f"unicode heartbeat glyph leaked into ASCII-mode control strip row: {row_text!r}"
    )
    assert "*" in row_text or "." in row_text, (
        f"expected an ASCII heartbeat twin in the control strip row, got {row_text!r}"
    )
    assert "→" in row_text, "→ is NO-SWAP (visual-language.md) -- must survive ASCII mode unchanged"
    assert _TX_IDLE in row_text


# ---------------------------------------------------------------------------
# Poll-guard: the LIVE 4th consumer-class extension (screens.py:477 area) --
# the real `minimal` tier previously polled zero times
# (tests/test_cockpit_hud_pty.py's own, now-updated, sibling test); with
# CONTROL_STRIP always present at this height it must poll exactly once.
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


def test_poll_guard_fires_at_minimal_tier_because_of_control_strip(monkeypatch):
    """LIVE, not latent (see ``screens.py``'s own comment on this 4th guard
    term): CONTROL_STRIP is present at every reachable non-``too_small``
    tier today (layout.py's own ``CONTROL_STRIP_H`` comment), INCLUDING the
    ``minimal`` tier where GOALS/DECISIONS/right_gutter are all ``None``
    together -- so the poll-guard must fire exactly once there now, where
    it previously fired zero times."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    minimal_rows, minimal_cols = 25, 100
    regions = frame_layout(minimal_rows, minimal_cols)
    assert regions["mode"] == "minimal"
    assert regions["goals"] is None
    assert regions["decisions"] is None
    assert regions["right_gutter"] is None
    assert regions["control_strip"] is not None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _NullWin(minimal_rows, minimal_cols)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"credits": 1}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1, (
        f"expected exactly one status_provider poll at the minimal tier now that "
        f"control_strip is a live status consumer there, got {len(calls)}"
    )


def test_poll_guard_still_never_double_polls_when_control_strip_joins_other_consumers(
    monkeypatch,
):
    """A tier where control_strip AND right_gutter/HUD are both present
    (the common case, e.g. the full tier) must still poll exactly once per
    draw -- the guard is a single boolean gate, not a per-consumer counter."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    assert regions["right_gutter"] is not None
    assert regions["control_strip"] is not None

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _NullWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile)

    calls: list[int] = []

    def _spy():
        calls.append(1)
        return {"credits": 1}

    screen.status_provider = _spy
    screen.draw()

    assert len(calls) == 1


# ---------------------------------------------------------------------------
# handle_key unchanged -- CONTROL_STRIP's wiring adds no new key handling.
# ---------------------------------------------------------------------------


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
# now_fn clock seam -- unit-level proof that a scripted now_fn is actually
# consulted at draw time (default resolves to time.monotonic when unset),
# independent of the pty proof above.
# ---------------------------------------------------------------------------


def test_now_fn_seam_feeds_the_liveness_composer(monkeypatch):
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    seen_now: list[float] = []
    real_compose = cockpit_liveness.compose_liveness_cluster

    def _spy_compose(status, *, now, width, unicode_ok=True):
        seen_now.append(now)
        return real_compose(status, now=now, width=width, unicode_ok=unicode_ok)

    monkeypatch.setattr(screens_mod.cockpit_liveness, "compose_liveness_cluster", _spy_compose)

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    screen = screens_mod.PlayShellScreen(
        _NullWin(FULL_ROWS, FULL_COLS), profile, now_fn=lambda: 42.0
    )
    screen.draw()

    assert seen_now == [42.0], f"expected the scripted now_fn's value to reach the composer, got {seen_now}"


class _RecordingWin(_NullWin):
    """Like ``_NullWin`` but records every ``addstr`` call's text -- needed
    here (unlike the poll-guard/handle_key unit tests above) to inspect
    what ``control_strip`` actually received, not just that ``draw()``
    completed without raising."""

    def __init__(self, rows: int, cols: int) -> None:
        super().__init__(rows, cols)
        self.calls: list[tuple[int, int, str]] = []

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text))


def test_raising_now_fn_does_not_crash_draw_and_cluster_still_renders(monkeypatch):
    """Mack finding, HIGH (directly reproduced): a raising ``now_fn`` --
    a public ``__init__`` kwarg, so any caller can hand in a broken one --
    must not escape ``draw()``, mirroring the containment already wrapped
    around ``status_provider()`` and every ``compose_*`` call in this same
    method. The fallback is the REAL ``time.monotonic()``, not a frozen
    ``0.0`` -- the heartbeat's whole job is proving the draw loop is still
    running (canon: "always breathing... so 'alive' reads even on a
    settled screen"); the loop demonstrably IS running here (draw()
    completed), so the true clock should surface rather than a fixed
    phase-0 lie. Proven at the real ``full`` tier by inspecting the actual
    ``addstr`` call the control strip row received -- not merely that no
    exception propagated."""
    from tw2002_aiclient import screens as screens_mod

    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)

    def _raising_now_fn():
        raise RuntimeError("clock seam is broken")

    profile = screens_mod.ProfileRow(
        name="alpha", handle=HANDLE, server="demo-a", host="demo-a.example", game_letter="B"
    )
    win = _RecordingWin(FULL_ROWS, FULL_COLS)
    screen = screens_mod.PlayShellScreen(win, profile, now_fn=_raising_now_fn)

    screen.draw()  # must not raise

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    control_strip = regions["control_strip"]
    assert control_strip is not None

    row_calls = [text for (y, _x, text) in win.calls if y == control_strip["y"]]
    assert row_calls, "expected an addstr call on the control strip row despite the raising now_fn"
    row_text = row_calls[-1]

    assert "●" in row_text or "○" in row_text, (
        f"expected a heartbeat glyph in the control strip row after the now_fn "
        f"fallback, got {row_text!r}"
    )
    assert _TX_IDLE in row_text
