"""Wire-level tests: ``PlayShellScreen.draw()`` actually PAINTS TWGS color
runs onto the GAME viewport (WO-P4-053 draw-seam wiring in ``screens.py``).

WO-P4-052 proved the viewport paints plain TEXT; WO-P4-053 lane 1
(``cockpit/viewport_color.py``) proved the pure geometry/pair-allocation
pieces in isolation; ``tests/test_screens_shared_pairs.py`` proved the
widened ``_SharedPairs`` allocator's own contract. This file proves the
seam that wires them together inside ``draw()`` itself: a known-palette
color map lands on the RIGHT cells with the RIGHT resolved attr, a
count-mismatched color map drops color but never drops TEXT, pair-table
exhaustion degrades to uncolored text without crashing a draw pass, and --
the regression class this whole merge exists to prevent -- chrome colors
survive GAME-cell allocation happening on the SAME shared allocator.

Same ``_RecordingWindow``/monochrome-avoidance convention as
``tests/test_cockpit_viewport_paint.py``, except here color support is
deliberately turned ON (``has_colors=True``) via a fake curses module
(``tests/test_screens_shared_pairs.py``'s own ``_FakeCurses``/
``_patch_curses``, imported rather than re-implemented) so real pair
allocation actually runs -- there is no live terminal in this process.
Each test installs a FRESH ``screens_mod._shared_pairs`` instance so pair
numbering never leaks across tests (mirrors a real process's own
process-lifetime singleton, just re-created per test instead of per
process).
"""

from __future__ import annotations

import curses

from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.screens import PlayShellScreen, ProfileRow

from .test_screens_shared_pairs import _FakeCurses, _patch_curses

FULL_ROWS, FULL_COLS = 40, 160


class _RecordingWindow:
    """Minimal addstr-only curses window double (curses test doubles are
    addstr-only in this project -- ``draw.py``'s ``_safe_write`` never
    calls ``addnstr``)."""

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


class _Snapshot:
    """Duck-typed ``WatchFeedSnapshot`` stand-in -- ``.latest_event`` only,
    same convention ``test_cockpit_viewport_paint_pty.py``'s own unit-level
    poll-guard test uses."""

    def __init__(self, latest_event):
        self.latest_event = latest_event


def _build_screen(monkeypatch, fake) -> tuple[PlayShellScreen, _RecordingWindow]:
    _patch_curses(monkeypatch, fake)
    monkeypatch.setattr(screens_mod, "_shared_pairs", screens_mod._SharedPairs())
    win = _RecordingWindow(FULL_ROWS, FULL_COLS)
    profile = ProfileRow(
        name="alpha", handle="Alpha", server="demo-a", host="demo-a.example", game_letter="B",
    )
    return PlayShellScreen(win, profile), win


def _interior():
    regions = frame_layout(FULL_ROWS, FULL_COLS)
    center = regions["center"]
    assert center is not None and center["border"] is True
    return center["y"] + 1, center["x"] + 1, center


def _calls_with_text(win: _RecordingWindow, text: str) -> list[tuple[int, int, str, int]]:
    return [c for c in win.calls if c[2] == text]


# ---------------------------------------------------------------------------
# (1) Known-palette fixture: colors land at the right cells with the right
# resolved attr, and the FULL uncolored text is still painted underneath.
# ---------------------------------------------------------------------------


def test_known_palette_lands_at_the_right_cells_with_the_right_attr(monkeypatch):
    fake = _FakeCurses()
    screen, win = _build_screen(monkeypatch, fake)
    pairs = screens_mod._shared_pairs  # the fresh instance _build_screen installed

    row0 = "GRNSPAN restofline"
    row1 = "second row BLUEBG here"
    event = {
        "screen": [row0, row1],
        "color": [
            [{"start": 0, "end": 7, "fg": "green", "bg": "default", "bold": False}],  # "GRNSPAN"
            [{"start": 11, "end": 17, "fg": "default", "bg": "blue", "bold": True}],  # "BLUEBG"
        ],
    }
    assert row0[0:7] == "GRNSPAN"
    assert row1[11:17] == "BLUEBG"

    screen.viewport_provider = lambda: _Snapshot(event)
    screen.draw()

    inner_y, inner_x, _center = _interior()

    # Base layer: the FULL row text painted uncolored underneath every run
    # -- content is never contingent on color succeeding.
    assert _calls_with_text(win, row0), f"expected full row0 text painted; calls={win.calls}"
    assert _calls_with_text(win, row1), f"expected full row1 text painted; calls={win.calls}"

    # Green run: exact segment, exact position, exact resolved attr (cache
    # hit against the SAME allocator draw() used -- no new pair consumed
    # by asking again).
    expected_green = pairs.attr_for("green", "default")
    green_calls = _calls_with_text(win, "GRNSPAN")
    assert green_calls == [(inner_y, inner_x + 0, "GRNSPAN", expected_green)]

    # Blue-bg bold run: same proof, plus the bold bit OR'd on top of the
    # allocator's own base (non-bold) attr.
    expected_blue = pairs.attr_for("default", "blue") | curses.A_BOLD
    blue_calls = _calls_with_text(win, "BLUEBG")
    assert blue_calls == [(inner_y + 1, inner_x + 11, "BLUEBG", expected_blue)]


# ---------------------------------------------------------------------------
# (2) A count mismatch between event["color"] and event["screen"] drops
# color entirely -- but the TEXT still paints. Proves both halves of the
# CALLER CONTRACT this file's own dispatch called out.
# ---------------------------------------------------------------------------


def test_color_screen_count_mismatch_drops_color_but_still_paints_text(monkeypatch):
    fake = _FakeCurses()
    screen, win = _build_screen(monkeypatch, fake)

    row0, row1 = "SHOULD-STILL-RENDER", "second row here"
    event = {
        "screen": [row0, row1],
        # Only ONE color row for TWO screen rows -- a genuine count
        # mismatch (e.g. a color map captured against a different, shorter
        # snapshot than the text).
        "color": [[{"start": 0, "end": 4, "fg": "red", "bg": "default", "bold": False}]],
    }

    pairs_calls_before = len(fake.init_pair_calls)  # chrome's own construction-time allocations
    screen.viewport_provider = lambda: _Snapshot(event)
    screen.draw()

    # Text unaffected -- both full rows still painted.
    assert _calls_with_text(win, row0)
    assert _calls_with_text(win, row1)

    # No color allocation was attempted for game cells at all -- the
    # mismatch was caught one layer up, before align_color_runs (let alone
    # run_attr) ever saw a run to resolve. Only chrome's own pre-existing
    # pairs (allocated at __init__) may appear.
    assert len(fake.init_pair_calls) == pairs_calls_before

    # And no cell painted the substring "SHOU" (the would-be colored
    # fragment) with a NON-zero attr -- if color leaked through despite
    # the mismatch, it would show up as a second, colored write over
    # position 0..4.
    colored_fragment_calls = [c for c in win.calls if c[2] == "SHOU" and c[3] != 0]
    assert colored_fragment_calls == []


# ---------------------------------------------------------------------------
# (3) Pair-table exhaustion degrades to uncolored text -- never crashes a
# draw pass.
# ---------------------------------------------------------------------------


def test_pair_exhaustion_degrades_to_uncolored_text_without_crash(monkeypatch):
    # Chrome's own __init__ allocates 2 pairs (cyan info, red danger) --
    # cap the table so NOTHING is left for GAME cells.
    fake = _FakeCurses(color_pairs_limit=3)  # pairs 1, 2 allocatable; pair 0 reserved
    screen, win = _build_screen(monkeypatch, fake)

    row0 = "EXHAUSTED-PALETTE-ROW"
    event = {
        "screen": [row0],
        "color": [[{"start": 0, "end": 9, "fg": "magenta", "bg": "white", "bold": False}]],
    }
    screen.viewport_provider = lambda: _Snapshot(event)

    screen.draw()  # must not raise

    # Text still painted in full.
    assert _calls_with_text(win, row0)
    # The would-be-colored segment ("EXHAUSTED") still painted, at
    # curses.A_NORMAL (0) -- degraded, not dropped, not crashed.
    segment_calls = [c for c in win.calls if c[2] == "EXHAUSTED"]
    assert segment_calls == [(_interior()[0], _interior()[1], "EXHAUSTED", curses.A_NORMAL)]


# ---------------------------------------------------------------------------
# (4) THE regression proof: chrome colors are unaffected by GAME-cell
# allocation happening on the same shared allocator, across repeated
# draw() calls.
# ---------------------------------------------------------------------------


def test_chrome_colors_survive_repeated_game_cell_allocation_across_draws(monkeypatch):
    fake = _FakeCurses()
    screen, win = _build_screen(monkeypatch, fake)

    chrome_attr_at_init = screen._chrome_attr
    danger_attr_at_init = screen._viewport_danger_attr
    # Chrome's own two pairs (info=cyan, danger=red) allocated at
    # construction -- capture their init_pair calls to diff against later.
    chrome_init_pair_calls = list(fake.init_pair_calls)
    assert len(chrome_init_pair_calls) == 2

    # First draw: no game provider -- HUD/DECISIONS boxes paint with
    # chrome's attrs.
    screen.draw()
    hud_region = frame_layout(FULL_ROWS, FULL_COLS)["right_gutter"]
    first_hud_border_calls = [
        c for c in win.calls
        if c[0] == hud_region["y"] and c[1] == hud_region["x"] and c[3] == chrome_attr_at_init
    ]
    assert first_hud_border_calls, "expected the HUD box's top border painted with the chrome attr"

    # A wave of distinct GAME-cell colors allocates across several draws --
    # deliberately varied fg/bg/bold combinations, none matching chrome's
    # own (cyan, default) or (red, default).
    palette = [
        ("green", "default", False),
        ("default", "blue", True),
        ("brown", "black", False),  # pyte's own yellow-quirk name
        ("magenta", "white", True),
        ("white", "green", False),
    ]
    for fg, bg, bold in palette:
        row = "GAME-COLOR-ROW"
        event = {
            "screen": [row],
            "color": [[{"start": 0, "end": len(row), "fg": fg, "bg": bg, "bold": bold}]],
        }
        screen.viewport_provider = lambda event=event: _Snapshot(event)
        win.calls.clear()
        screen.draw()

    # Chrome's own already-allocated pairs were NEVER re-init_pair'd with a
    # different color, no matter how many GAME-cell combos allocated in
    # between -- the exact corruption class Mack's original PoC caught
    # between two independent allocators, reproduced here between chrome
    # and game cells sharing ONE.
    for call in chrome_init_pair_calls:
        pair_n = call[0]
        same_pair_calls = [c for c in fake.init_pair_calls if c[0] == pair_n]
        assert same_pair_calls == [call], (
            f"chrome pair {pair_n} was re-initialized: {same_pair_calls} (expected only {[call]})"
        )

    # And the cached attr ints themselves are byte-for-byte unchanged --
    # never recomputed, never drifted.
    assert screen._chrome_attr == chrome_attr_at_init
    assert screen._viewport_danger_attr == danger_attr_at_init

    # Final draw with chrome-only content again: HUD box still paints with
    # the SAME attr as the very first draw.
    screen.viewport_provider = None
    win.calls.clear()
    screen.draw()
    final_hud_border_calls = [
        c for c in win.calls
        if c[0] == hud_region["y"] and c[1] == hud_region["x"] and c[3] == chrome_attr_at_init
    ]
    assert final_hud_border_calls, "expected the HUD box still painted with the ORIGINAL chrome attr"


# ---------------------------------------------------------------------------
# (5) Hostile CSI/OSC survives containment through the color-aware path too
# -- draw_runs routes both the base layer and every colored run through
# the same _safe_write/_clip_cells choke point every other panel uses.
# ---------------------------------------------------------------------------


def test_hostile_escape_payload_neutralized_even_under_a_color_run(monkeypatch):
    fake = _FakeCurses()
    screen, win = _build_screen(monkeypatch, fake)

    hostile_row = "MARK \x1b[31mRED\x1b[0m \x1b]0;evil-title\x07TAIL"
    event = {
        "screen": [hostile_row],
        # A color run deliberately overlapping the escape bytes.
        "color": [[{"start": 0, "end": len(hostile_row), "fg": "red", "bg": "default", "bold": False}]],
    }
    screen.viewport_provider = lambda: _Snapshot(event)

    screen.draw()  # must not raise

    # No raw ESC (0x1b) or BEL (0x07) byte survives into ANY recorded
    # write -- both the uncolored base layer and the colored overlay run
    # through _safe_write's control-char neutralization.
    for _y, _x, text, _attr in win.calls:
        assert "\x1b" not in text
        assert "\x07" not in text

    # The literal, harmless remnant of the neutralized escape (a plain
    # space in place of ESC) survives as ordinary text -- containment, not
    # silent deletion.
    full_text = "".join(c[2] for c in win.calls)
    assert "MARK" in full_text
    assert "[31mRED" in full_text
    assert "TAIL" in full_text
