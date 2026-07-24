"""PWO-051 -- GAME viewport shell draw-path proof (Layer-A, pure fake
window, no pty/curses init needed).

Complements the pure-geometry PWO-051 coverage in
``tests/test_cockpit_layout.py`` (the interior content-budget math) and the
pty grid-blank proof in ``tests/test_cockpit_frame_pty.py`` (what a real
terminal actually renders) -- this file proves the thing neither of those
can: that ``PlayShellScreen.draw()`` itself never issues an ``addstr`` call
that lands inside the GAME box's own interior cells, and that the retired
``_GAME_PLACEHOLDER`` string (or any text containing the word
"placeholder") never reaches any ``addstr`` call anywhere in a full draw
pass. Proven directly at the real ``draw()`` call via a fake stdscr
recording every write -- ``draw.py``'s own ``_safe_write`` only ever calls
``getmaxyx``/``addstr`` on its window argument (mirrors
``tests/test_play_chrome_nav.py``'s ``_RecordingStdscr`` addstr-only
surface, per this project's own "curses test doubles are addstr-only"
convention).
"""

from __future__ import annotations

from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow

# Matches tests/test_cockpit_frame_pty.py's own full-tier fixture size --
# same "full" mode, same center geometry, so results are directly
# comparable to that suite's pty-grid proof.
ROWS, COLS = 40, 160


class _RecordingWindow:
    """Minimal addstr-only curses window double: records every write's
    ``(y, x, text, attr)``. No ``addnstr`` on purpose -- ``draw.py``'s own
    ``_safe_write`` never calls it (see that module's docstring)."""

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


def _draw_full_tier(monkeypatch) -> _RecordingWindow:
    # Monochrome path -- avoids real curses.start_color()/init_pair() state,
    # same monkeypatch shape as tests/test_play_chrome_nav.py's
    # test_run_play_esc_returns_back_without_stopping_fake_session; colors
    # are irrelevant to what this file proves (text/position only).
    monkeypatch.setattr("tw2002_aiclient.screens.curses.has_colors", lambda: False)
    win = _RecordingWindow(ROWS, COLS)
    profile = ProfileRow(
        name="alpha",
        handle="Alpha",
        server="demo-a",
        host="demo-a.example",
        game_letter="B",
    )
    screen = PlayShellScreen(win, profile)
    screen.draw()
    return win


def test_no_addstr_call_writes_into_the_game_interior_cells(monkeypatch):
    """Bordered full tier: only the double-line border + 'GAME' title write
    into the center region at all (both land on the box's OWN border rows,
    never the interior) -- the interior stays completely untouched, the
    honest-blank-grid Accept criterion (PREP §PWO-051)."""
    win = _draw_full_tier(monkeypatch)
    regions = frame_layout(ROWS, COLS)
    center = regions["center"]
    assert center["border"] is True  # confirms this size is the bordered tier this test targets

    interior_rows = range(center["y"] + 1, center["y"] + center["h"] - 1)
    interior_cols = range(center["x"] + 1, center["x"] + center["w"] - 1)
    interior_col_set = set(interior_cols)

    offenders = []
    for y, x, text, _attr in win.calls:
        if not text or y not in interior_rows:
            continue
        # Check every cell the write's text will occupy, not just its start
        # cell -- a write starting just outside the interior could still
        # bleed into it (defense in depth; no such write exists today, but
        # the assertion should catch one if it ever regressed).
        touched = range(x, x + len(text))
        if interior_col_set & set(touched):
            offenders.append((y, x, text))

    assert offenders == [], f"addstr call(s) wrote into the GAME interior: {offenders}"


def test_placeholder_string_never_reaches_any_addstr_call(monkeypatch):
    """The retired placeholder text must not reach ANY addstr call in a
    full draw pass -- not just absent from the GAME box, grid-wide (mirrors
    tests/test_cockpit_frame_pty.py's own grid-wide assertion, proven here
    at the draw-call level instead of a rendered pty grid)."""
    win = _draw_full_tier(monkeypatch)
    offenders = [(y, x, text) for y, x, text, _attr in win.calls if "placeholder" in text.lower()]
    assert offenders == [], f"'placeholder' reached addstr call(s): {offenders}"
