"""Layer-A tests for the GAME viewport paint composer (WO-P4-052).

Pure composer tests plus wire-level poll-guard/paint tests only -- no pty/
real terminal (that is the sibling ``tests/test_cockpit_viewport_paint_pty.py``,
a separate file this one does not touch). Mirrors the pure-composer test
convention established by ``tests/test_cockpit_logsband.py``/
``tests/test_cockpit_goals.py``, the addstr-recording wire-level pattern
from ``tests/test_cockpit_viewport.py`` (PWO-051's own shell proof), and the
poll-guard spy pattern from ``tests/test_cockpit_liveness_pty.py``.
"""

from __future__ import annotations

from tw2002_aiclient.cockpit.layout import GAME_H, GAME_W, frame_layout
from tw2002_aiclient.cockpit.viewport import compose_viewport_lines
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow
from tw2002_aiclient.watchfeed import WatchFeedSnapshot

# ---------------------------------------------------------------------------
# compose_viewport_lines -- pure composer
# ---------------------------------------------------------------------------


def test_fixture_grid_composes_to_exact_expected_lines():
    grid = ["Command [TL=00:00:00]:[1] (?=Help)? :", "Sector  : 1", "Ports   : 0"]
    result = compose_viewport_lines({"screen": list(grid)}, width=GAME_W, height=GAME_H)
    assert result == grid


def test_over_wide_rows_clip_to_width():
    event = {"screen": ["x" * 100, "y" * 50]}
    assert compose_viewport_lines(event, width=80, height=25) == ["x" * 80, "y" * 50]


def test_over_tall_input_keeps_last_height_rows_top_drop():
    # 30 rows, only 25 fit -- the LAST 25 must survive (rows 5..29,
    # 0-indexed), never rows 0..4. Row 29 is the "prompt" row an operator
    # most needs under height pressure -- it must be present in the
    # output; a top row (row00) must be gone. This is the ruled TOP-DROP
    # policy (screens.py's convention doc), the opposite of the archive's
    # bottom-drop.
    grid = [f"row{i:02d}" for i in range(30)]
    result = compose_viewport_lines({"screen": grid}, width=80, height=25)
    assert len(result) == 25
    assert result[-1] == "row29"  # bottom/prompt row survives
    assert "row00" not in result  # a top row was shed
    assert result == grid[-25:]


def test_exactly_fitting_input_is_unchanged():
    grid = [f"row{i:02d}" for i in range(25)]
    assert compose_viewport_lines({"screen": grid}, width=80, height=25) == grid


def test_under_height_input_is_unchanged_no_padding():
    grid = ["only one row"]
    assert compose_viewport_lines({"screen": grid}, width=80, height=25) == grid


def test_none_event_is_honest_empty():
    assert compose_viewport_lines(None, width=80, height=25) == []


def test_non_dict_event_is_honest_empty():
    assert compose_viewport_lines("nope", width=80, height=25) == []
    assert compose_viewport_lines(42, width=80, height=25) == []
    assert compose_viewport_lines(object(), width=80, height=25) == []


def test_missing_screen_key_is_honest_empty():
    assert compose_viewport_lines({}, width=80, height=25) == []


def test_screen_not_a_list_is_honest_empty():
    assert compose_viewport_lines({"screen": "nope"}, width=80, height=25) == []
    assert compose_viewport_lines({"screen": None}, width=80, height=25) == []
    assert compose_viewport_lines({"screen": {}}, width=80, height=25) == []
    assert compose_viewport_lines({"screen": 5}, width=80, height=25) == []


def test_a_single_non_str_row_invalidates_the_whole_grid():
    # Unlike logsband.py's per-entry coercion, ONE hostile row here degrades
    # the ENTIRE result to empty -- a screen grid's rows are positionally
    # meaningful relative to each other, unlike a flat transcript's entries
    # (see the composer module's own docstring).
    assert compose_viewport_lines({"screen": ["ok row", 42]}, width=80, height=25) == []
    assert compose_viewport_lines({"screen": ["ok row", None]}, width=80, height=25) == []

    class HostileStr:
        def __str__(self):
            raise RuntimeError("boom")

    assert compose_viewport_lines({"screen": ["ok row", HostileStr()]}, width=80, height=25) == []


def test_width_or_height_non_positive_is_empty():
    grid = ["a row"]
    assert compose_viewport_lines({"screen": grid}, width=0, height=25) == []
    assert compose_viewport_lines({"screen": grid}, width=-1, height=25) == []
    assert compose_viewport_lines({"screen": grid}, width=80, height=0) == []
    assert compose_viewport_lines({"screen": grid}, width=80, height=-1) == []


def test_hostile_width_height_types_degrade_to_empty_not_raise():
    grid = ["a row"]
    assert compose_viewport_lines({"screen": grid}, width="nope", height=25) == []
    assert compose_viewport_lines({"screen": grid}, width=float("inf"), height=25) == []
    assert compose_viewport_lines({"screen": grid}, width=80, height=object()) == []


# ---------------------------------------------------------------------------
# Wire-level: PlayShellScreen.draw() polls viewport_provider once and paints
# ---------------------------------------------------------------------------

FULL_ROWS, FULL_COLS = 40, 160


class _RecordingWindow:
    """Minimal addstr-only curses window double -- matches
    ``tests/test_cockpit_viewport.py``'s own double (``draw.py``'s
    ``_safe_write`` never calls ``addnstr``, per this project's "curses
    test doubles are addstr-only" convention)."""

    def __init__(self, rows: int, cols: int) -> None:
        self._rows, self._cols = rows, cols
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self._rows, self._cols

    def erase(self) -> None:
        pass

    def refresh(self) -> None:
        pass

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))


def _build_screen(monkeypatch) -> tuple[PlayShellScreen, _RecordingWindow]:
    # Monochrome path -- avoids real curses.start_color()/init_pair() state,
    # same monkeypatch shape as tests/test_cockpit_viewport.py.
    monkeypatch.setattr("tw2002_aiclient.screens.curses.has_colors", lambda: False)
    win = _RecordingWindow(FULL_ROWS, FULL_COLS)
    profile = ProfileRow(
        name="alpha", handle="Alpha", server="demo-a", host="demo-a.example", game_letter="B",
    )
    return PlayShellScreen(win, profile), win


def _interior_offenders(win: _RecordingWindow, center: dict) -> list[tuple[int, int, str]]:
    """Every recorded write that touches (any cell of) the GAME box's own
    interior -- mirrors ``tests/test_cockpit_viewport.py``'s own scan."""
    interior_rows = range(center["y"] + 1, center["y"] + center["h"] - 1)
    interior_cols = set(range(center["x"] + 1, center["x"] + center["w"] - 1))
    offenders = []
    for y, x, text, _attr in win.calls:
        if not text or y not in interior_rows:
            continue
        touched = range(x, x + len(text))
        if interior_cols & set(touched):
            offenders.append((y, x, text))
    return offenders


def test_draw_calls_viewport_provider_exactly_once_and_paints_its_content(monkeypatch):
    screen, win = _build_screen(monkeypatch)

    calls: list[int] = []
    grid = ["Command [TL=00:00:00]:[1] (?=Help)? :", "second row"]

    def _spy():
        calls.append(1)
        return WatchFeedSnapshot(events_received=1, latest_event={"screen": grid}, running=True)

    screen.viewport_provider = _spy
    screen.draw()

    assert len(calls) == 1, f"expected exactly one viewport_provider poll per draw, got {len(calls)}"

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert center["border"] is True
    interior_y, interior_x = center["y"] + 1, center["x"] + 1

    for i, expected_text in enumerate(grid):
        matches = [
            (y, x, text, attr)
            for y, x, text, attr in win.calls
            if y == interior_y + i and x == interior_x and text == expected_text
        ]
        assert matches, (
            f"expected row {i} ({expected_text!r}) painted at "
            f"(y={interior_y + i}, x={interior_x}); calls={win.calls}"
        )


def test_draw_paints_nothing_when_no_provider_set(monkeypatch):
    """Matches PWO-051's own contract, re-proven here at the paint call
    site: no ``viewport_provider`` set -> the interior stays untouched,
    same as ``tests/test_cockpit_viewport.py``'s pre-WO-P4-052 proof."""
    screen, win = _build_screen(monkeypatch)
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert _interior_offenders(win, center) == []


def test_draw_paints_nothing_when_provider_returns_none_event(monkeypatch):
    screen, win = _build_screen(monkeypatch)
    screen.viewport_provider = lambda: WatchFeedSnapshot(
        events_received=0, latest_event=None, running=True
    )
    screen.draw()

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert _interior_offenders(win, center) == []


def test_raising_provider_does_not_crash_draw_and_leaves_interior_blank(monkeypatch):
    screen, win = _build_screen(monkeypatch)

    def _boom():
        raise RuntimeError("boom")

    screen.viewport_provider = _boom
    screen.draw()  # must not raise

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert _interior_offenders(win, center) == []


def test_provider_returning_object_without_latest_event_does_not_crash_draw(monkeypatch):
    """A provider that doesn't honor the ``WatchFeedSnapshot`` duck-type
    (no ``.latest_event`` attribute) must degrade the same as any other
    unusable provider result, never crash the draw pass."""
    screen, win = _build_screen(monkeypatch)
    screen.viewport_provider = lambda: object()
    screen.draw()  # must not raise

    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert _interior_offenders(win, center) == []
