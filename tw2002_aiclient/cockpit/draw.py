"""Curses chrome renderer for the trainer-cockpit frame (PWO-031/033,
``workorders/WO-P3-030-033-cockpit-frame-PREP.md``).

Consumes ``tw2002_aiclient.cockpit.layout.frame_layout()`` region dicts only
-- no duplicate geometry math lives here, per the PREP's D2 boundary between
the pure layout module and this drawing module. Two-weight border system
per ``canon/surfaces/visual-language.md`` ("Box-drawing / border
hierarchy"): double-line for the outer frame + the game viewport (when
bordered), thin-rounded for every instrument box (PRIORITIES/HUD/LOGS).
Unicode/ASCII both switch on the single ``unicode_ok()`` flag below, mirroring
``screens.py``'s existing ``_unicode_ok()``/``TW2002_ASCII=1`` convention.

Every write goes through ``_safe_write``: control-char neutralization, a
cell-width-aware length clip (never reaches past the window's last display
column -- east-asian-wide content is measured in terminal cells, not Python
characters, stdlib-only via ``unicodedata``, no ``wcwidth`` dependency), and
a ``try/except curses.error`` around the underlying ``addstr`` call. The clip
alone does not eliminate the classic curses "bottom-right cell" quirk --
writing a box's own corner glyph at the window's true bottom-right cell
(``max_y-1, max_x-1``) still raises ``curses.error`` after the character has
already been placed, because advancing the cursor past the window would
fail. That throw is expected, not a bug (PREP §3 guard #1); catching and
ignoring it is what lets the outer frame's own bottom-right corner glyph
render at all. ``addstr`` (not ``addnstr``) is used deliberately so this
module works against any minimal stdscr double that implements
``addstr``/``getmaxyx`` without a full ``addnstr`` surface (see
``tests/test_play_chrome_nav.py::_RecordingStdscr``).

Every write is a single terminal row, always. This matters because two
untrusted-content hazards both come down to "did the write actually stay on
one row, inside its own box": (1) a CJK/wide-glyph-heavy string measured in
Python-character count rather than terminal cells can occupy more display
columns than its budget, physically overwriting a box's own right border;
(2) a raw control character -- most concretely an embedded ``\n`` -- inside
content that reaches this module (e.g. a caller's free-text status line)
moves the terminal cursor itself when ``addstr`` prints it, escaping the
target box's own left/top inset entirely. ``_safe_write`` neutralizes every
control char to a plain space (preserving alignment -- runs are not
collapsed) before the cell-width clip runs, so untrusted content can never
do either.

No ``newwin`` here -- chrome draws directly onto the caller's stdscr on
every ``draw()`` call. Persistent per-pane windows rebuilt only on
``KEY_RESIZE``/tier-change (PREP §3 guard #5) is a concern for the later,
animated-viewport WO that owns the ~13fps chrome tick; this module has no
tick of its own to decouple from.
"""

from __future__ import annotations

import os
import unicodedata
from typing import Sequence

import curses

# Every C0 control (\x00-\x1f) and C1 control (\x7f-\x9f) maps to a single
# plain space -- alignment-preserving (no run-collapse), stdlib str.translate.
# \n in particular would otherwise move the real terminal cursor when
# addstr prints it, escaping whatever box the caller thought it was
# confined to (see the module docstring).
_CONTROL_CHAR_TRANSLATION = {c: " " for c in range(0x00, 0x20)}
_CONTROL_CHAR_TRANSLATION.update({c: " " for c in range(0x7F, 0xA0)})


def _sanitize_controls(text: str) -> str:
    return text.translate(_CONTROL_CHAR_TRANSLATION)


def _cell_width(ch: str) -> int:
    """Terminal display width of one character: 2 cells for East-Asian
    Wide/Fullwidth, 1 otherwise (stdlib ``unicodedata`` only -- no
    ``wcwidth`` dependency; box-drawing glyphs are category "A" (Ambiguous),
    which stays 1-cell here, matching how every non-CJK-locale terminal in
    this project's target environment renders them)."""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _clip_cells(text: str, cells: int) -> str:
    """Clip ``text`` to at most ``cells`` display columns, cutting at the
    last character that fully fits -- never slices a wide character in
    half."""
    if cells <= 0:
        return ""
    out: list[str] = []
    used = 0
    for ch in text:
        w = _cell_width(ch)
        if used + w > cells:
            break
        out.append(ch)
        used += w
    return "".join(out)

# -- two-weight glyph tables (visual-language.md "Box-drawing hierarchy") --
# viewport / outer frame: double-line. Every instrument box: thin-rounded.
DOUBLE_UNICODE = {
    "tl": "╔",  # ╔
    "tr": "╗",  # ╗
    "bl": "╚",  # ╚
    "br": "╝",  # ╝
    "h": "═",  # ═
    "v": "║",  # ║
}
DOUBLE_ASCII = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "=", "v": "|"}

THIN_UNICODE = {
    "tl": "╭",  # ╭
    "tr": "╮",  # ╮
    "bl": "╰",  # ╰
    "br": "╯",  # ╯
    "h": "─",  # ─
    "v": "│",  # │
}
THIN_ASCII = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"}


def unicode_ok() -> bool:
    """ASCII force via ``TW2002_ASCII=1`` -- mirrors ``screens.py``'s launcher
    convention so every cockpit glyph degrades on the same single flag."""
    return os.environ.get("TW2002_ASCII", "").strip() != "1"


def _glyphs(weight: str, *, uok: bool) -> dict[str, str]:
    if weight == "double":
        return DOUBLE_UNICODE if uok else DOUBLE_ASCII
    return THIN_UNICODE if uok else THIN_ASCII


def _safe_write(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    """Bounded, guarded single write -- see the module docstring for why the
    corner-cell ``curses.error`` is caught rather than avoided by truncation,
    and why control chars are neutralized before the cell-width clip."""
    if not text:
        return
    try:
        max_y, max_x = win.getmaxyx()
    except curses.error:
        return
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    clipped = _clip_cells(_sanitize_controls(text), max(0, max_x - x))
    if not clipped:
        return
    try:
        win.addstr(y, x, clipped, attr)
    except curses.error:
        pass  # bottom-right-cell throw is EXPECTED, not a bug (PREP §3 guard #1)


def draw_box(
    win: curses.window,
    region: dict | None,
    *,
    weight: str,
    attr: int,
    title: str | None = None,
    title_attr: int | None = None,
    uok: bool | None = None,
) -> None:
    """Draw one bordered box from a ``frame_layout()`` region dict.

    ``weight`` is ``"double"`` (outer frame / bordered game viewport) or
    ``"thin"`` (every instrument box). A ``title`` is written at the box's
    own ``(0, 2)`` -- i.e. ``(region.y, region.x + 2)`` -- wrapped in a
    single space on each side, per the canon titling convention shared by
    every titled box on every surface.
    """
    if region is None:
        return
    y, x, w, h = region["y"], region["x"], region["w"], region["h"]
    if w < 2 or h < 2:
        return
    if uok is None:
        uok = unicode_ok()
    g = _glyphs(weight, uok=uok)

    top = g["tl"] + g["h"] * (w - 2) + g["tr"]
    bottom = g["bl"] + g["h"] * (w - 2) + g["br"]
    _safe_write(win, y, x, top, attr)
    _safe_write(win, y + h - 1, x, bottom, attr)
    for row in range(y + 1, y + h - 1):
        _safe_write(win, row, x, g["v"], attr)
        _safe_write(win, row, x + w - 1, g["v"], attr)

    if title:
        # Clip to the box's OWN interior budget, not just the window's edge
        # -- _safe_write's clip alone only guards the window's true right
        # column, which for a narrow interior box sits far past this box's
        # own right border; an unclipped overlong title would otherwise
        # bleed past this box's corner into whatever sits to its right.
        # Budget derivation: the padded " {title} " write starts at offset 2
        # (x+2) and must not reach offset w-1 (the right corner) --
        # 2 + (clipped_len + 2) - 1 <= w - 2 => clipped_len <= w - 5.
        clipped_title = _clip_cells(title, max(0, w - 5))
        _safe_write(win, y, x + 2, f" {clipped_title} ", title_attr if title_attr is not None else attr)


def draw_lines(
    win: curses.window,
    region: dict | None,
    lines: Sequence[str],
    attr: int,
    *,
    boxed: bool = True,
) -> None:
    """Write content lines inside a region -- inset by one cell on every
    side when ``boxed`` (the region carries its own border, drawn
    separately via ``draw_box``), or filling the raw region when not
    (``no_border`` tier / the row-1 strip, which owns no border of its
    own). Lines beyond the available interior height are silently dropped;
    each line is clipped to the interior width."""
    if region is None or not lines:
        return
    y, x, w, h = region["y"], region["x"], region["w"], region["h"]
    if boxed:
        inner_y, inner_x, inner_w, inner_h = y + 1, x + 1, w - 2, h - 2
    else:
        inner_y, inner_x, inner_w, inner_h = y, x, w, h
    if inner_w < 1 or inner_h < 1:
        return
    for i, line in enumerate(lines):
        if i >= inner_h:
            break
        _safe_write(win, inner_y + i, inner_x, _clip_cells(line, inner_w), attr)


def draw_refuse_message(win: curses.window, message: str, attr: int) -> None:
    """``mode == "too_small"``: render the layout's refusal message and
    nothing else (no chrome glyphs, no panels) -- caller must ``erase()``
    first the same as any other draw pass."""
    _safe_write(win, 0, 0, message or "", attr)
