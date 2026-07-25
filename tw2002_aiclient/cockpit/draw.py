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

``safe_write`` (module-public; ``_safe_write`` remains as an internal alias
so existing in-module callers are untouched) is THE ONE coordinate-write
primitive for every screen family in this project -- cockpit panels AND,
per ``WO-AUDIT-SAFE-ADDSTR-DEDUPE``, ``screens.py``'s pre-cockpit launcher/
bank/create-profile forms, which used to carry their own less-hardened
``_safe_addstr`` twin. Every write goes through it: control-char
neutralization, a cell-width-aware length clip (never reaches past the
window's last display column -- east-asian-wide content is measured in
terminal cells, not Python characters, stdlib-only via ``unicodedata``, no
``wcwidth`` dependency), and a ``try/except curses.error`` around the
underlying ``addstr`` call. The clip
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


def safe_write(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    """Bounded, guarded single write -- see the module docstring for why the
    corner-cell ``curses.error`` is caught rather than avoided by truncation,
    and why control chars are neutralized before the cell-width clip. THE
    ONE coordinate-write primitive for every screen family -- see the
    module docstring."""
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


# Internal alias -- every in-module caller below keeps spelling it
# ``_safe_write``, unchanged by this WO's public export.
_safe_write = safe_write


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


def draw_lines_attrs(
    win: curses.window,
    region: dict | None,
    lines: Sequence[tuple[str, int]],
    *,
    boxed: bool = True,
) -> None:
    """Like ``draw_lines``, but each line carries its OWN curses attr rather
    than one flat attr for the whole box -- the shape a panel needs when
    only SOME of its lines should render differently from the rest (HUD's
    freshness dimming: a stale value row's ``curses.A_DIM`` beside its
    label's ``curses.A_NORMAL``, same box, PWO-037).

    Identical inset math to ``draw_lines`` -- inset by one cell on every
    side when ``boxed``, or filling the raw region when not -- and the
    identical safety discipline: every line is clipped to the box's own
    interior width via ``_clip_cells`` (cell-width-aware, never just the
    window's edge -- an unclipped line would otherwise bleed past this
    box's own right border) BEFORE reaching ``_safe_write``, which then
    neutralizes embedded control characters and guards the underlying
    ``addstr`` call. Both hazards this guards against are wire-reachable:
    an untrusted free-text value can carry CJK/fullwidth glyphs (measured
    in cells, not Python characters) or a raw control sequence (e.g. an
    embedded ``\\n`` that would otherwise move the real terminal cursor and
    escape the box). Lines beyond the available interior height are
    silently dropped, same as ``draw_lines``.
    """
    if region is None or not lines:
        return
    y, x, w, h = region["y"], region["x"], region["w"], region["h"]
    if boxed:
        inner_y, inner_x, inner_w, inner_h = y + 1, x + 1, w - 2, h - 2
    else:
        inner_y, inner_x, inner_w, inner_h = y, x, w, h
    if inner_w < 1 or inner_h < 1:
        return
    for i, (line, attr) in enumerate(lines):
        if i >= inner_h:
            break
        _safe_write(win, inner_y + i, inner_x, _clip_cells(line, inner_w), attr)


def _cell_index_map(text: str) -> list[tuple[int, int]]:
    """``(cell_start, cell_width)`` for every character of ``text``, in
    order -- the per-character cell-column table ``_slice_by_cell`` walks
    to pull out a sub-line span without slicing a wide character in
    half. Shares ``_cell_width``'s East-Asian-Wide/Fullwidth-is-2-cells
    rule with every other clip in this module."""
    out: list[tuple[int, int]] = []
    used = 0
    for ch in text:
        w = _cell_width(ch)
        out.append((used, w))
        used += w
    return out


def _slice_by_cell(
    text: str, cell_map: list[tuple[int, int]], start: int, end: int
) -> tuple[int | None, str]:
    """The substring of ``text`` whose characters fall FULLY within the
    cell-column range ``[start, end)`` -- a character straddling either
    edge (most concretely a wide glyph whose 2-cell span only partly
    overlaps the run) is dropped whole rather than sliced, same
    discipline as ``_clip_cells``. ``cell_map`` is ``_cell_index_map(text)``
    for this same string, passed in so painting several runs against one
    line only pays the walk once.

    Returns ``(offset, substring)`` -- ``offset`` is the cell-column of
    the FIRST character actually included, which can be greater than
    ``start`` when the character sitting at ``start`` itself got dropped
    (e.g. ``start`` lands inside a wide glyph's own 2-cell span, so that
    glyph is skipped and the substring begins at the next real
    character). A caller writing the substring MUST use this returned
    offset as its screen x-position, never the raw ``start`` -- writing
    at ``start`` in that dropped-leading-character case would place the
    surviving text one cell to the left of where it actually sits on the
    line. ``(None, "")`` when nothing in range survives."""
    out = []
    offset = None
    for ch, (cell_start, cell_w) in zip(text, cell_map):
        if cell_start >= end:
            break
        if cell_start >= start and cell_start + cell_w <= end:
            if offset is None:
                offset = cell_start
            out.append(ch)
    return offset, "".join(out)


def _coerce_run(run) -> tuple[int, int, int] | None:
    """Best-effort ``(start, end, attr)`` int coercion for one run dict --
    ``None`` on anything unusable: not a dict, a missing ``start``/``end``,
    a non-finite/unparsable numeric (``int(float("nan"))``/``int(float
    ("inf"))`` both raise, one ``ValueError`` and one ``OverflowError`` --
    see this project's own "``_safe_int`` must catch ``OverflowError``"
    lesson), or an empty/inverted span (``end <= start``). A run missing
    ``attr`` entirely defaults to ``0`` -- indistinguishable from the
    uncolored base layer ``draw_runs`` already painted, so that's a safe
    default rather than a reason to drop the run."""
    if not isinstance(run, dict):
        return None
    try:
        start = int(run["start"])
        end = int(run["end"])
        attr = int(run.get("attr", 0))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if end <= start:
        return None
    return start, end, attr


def draw_runs(
    win: curses.window,
    region: dict | None,
    lines: Sequence[tuple[str, Sequence[dict] | None]],
    *,
    boxed: bool = True,
) -> None:
    """Per-RUN, sub-line curses attrs -- the shape a color-aware panel
    needs when DIFFERENT SPANS of the same line carry different attrs
    (TWGS SGR color runs painted onto the GAME viewport, WO-P4-053),
    where ``draw_lines`` (one attr for the whole box) and
    ``draw_lines_attrs`` (one attr per LINE) both fall short.

    ``lines`` pairs each line's full text with its own run list -- each
    run a ``{"start", "end" (exclusive), "attr"}`` dict describing a
    cell-column span within THAT line, the same run shape
    ``TerminalScreen.color_map()`` emits (see that method's own
    docstring: rows/runs are meant to be zipped by index against the
    SAME rows a caller got from ``render_with_color()``). Every line is
    first written in full at ``attr=0`` -- the same safe write
    ``draw_lines_attrs`` would produce for it -- and each VALID run is
    then overlaid on top with its own attr. That means a line with no
    runs, an empty run list, or a run list that doesn't fully cover the
    line's width all still render their complete text; only the color
    is missing wherever no valid run says otherwise. A malformed
    individual run entry (missing/wrong-typed keys, an empty or inverted
    span, a non-finite numeric) is silently dropped by ``_coerce_run`` --
    degrading that one span to the uncolored base layer -- rather than
    raising or voiding the rest of the line. Never raises, same
    hardening family as every other draw in this module.

    Identical inset math to ``draw_lines``/``draw_lines_attrs``: inset by
    one cell on every side when ``boxed``, filling the raw region when
    not; lines beyond the available interior height are silently
    dropped. A run's own span is clipped to the visible interior bounds
    (cell-width-aware, via ``_slice_by_cell`` -- never just the window's
    edge, matching ``draw_box``'s title-clip reasoning) BEFORE reaching
    ``_safe_write``, so a run straddling the region's right edge
    truncates cleanly instead of bleeding past this box's own border;
    ``_safe_write`` itself still neutralizes control characters and
    guards the underlying ``addstr`` call, same as every other write
    here.
    """
    if region is None or not lines:
        return
    y, x, w, h = region["y"], region["x"], region["w"], region["h"]
    if boxed:
        inner_y, inner_x, inner_w, inner_h = y + 1, x + 1, w - 2, h - 2
    else:
        inner_y, inner_x, inner_w, inner_h = y, x, w, h
    if inner_w < 1 or inner_h < 1:
        return
    for i, item in enumerate(lines):
        if i >= inner_h:
            break
        try:
            text, runs = item
        except (TypeError, ValueError):
            continue
        if not isinstance(text, str):
            continue
        row_y = inner_y + i
        # Base layer: the full line, uncolored -- guarantees content is
        # never lost even when every run below turns out unusable.
        _safe_write(win, row_y, inner_x, _clip_cells(text, inner_w), 0)
        if not runs:
            continue
        try:
            run_list = list(runs)
        except TypeError:
            continue
        cell_map = _cell_index_map(text)
        for raw_run in run_list:
            coerced = _coerce_run(raw_run)
            if coerced is None:
                continue
            start, end, attr = coerced
            vis_start = max(0, start)
            vis_end = min(end, inner_w)
            if vis_end <= vis_start:
                continue
            offset, segment = _slice_by_cell(text, cell_map, vis_start, vis_end)
            if not segment:
                continue
            _safe_write(win, row_y, inner_x + offset, segment, attr)


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
    each line is clipped to the interior width.

    Delegates to ``draw_lines_attrs`` with ``attr`` repeated for every
    line -- the flat-attr convenience shape every existing caller
    (GOALS/FOCUS/DECISIONS/the strip/GAME/LOGS) uses; behavior is
    unchanged from before this delegation existed."""
    draw_lines_attrs(win, region, [(line, attr) for line in lines], boxed=boxed)


def draw_segment_line(
    win: curses.window,
    region: dict | None,
    segments: Sequence[tuple[str, int]],
    *,
    boxed: bool = False,
) -> None:
    """Render ONE row composed of ordered ``(text, attr)`` segments, each run
    painted with its own curses attr -- the shape ``draw_lines_attrs`` (one
    attr per whole LINE) can't express when a SINGLE line needs different
    attrs on different spans (WO-P5-060: the control strip's App/Human
    mode-badge chip needs its own reverse-video+tone attr distinct from the
    row's liveness cluster, which stays plain).

    Segments are written left-to-right through the SAME ``_clip_cells``/
    ``_safe_write`` choke every other draw in this module uses, with the
    row's own interior width budget (``inner_w``, identical inset math to
    ``draw_lines``/``draw_lines_attrs``: inset one cell on every side when
    ``boxed``, or filling the raw region when not) tracked as a single
    running ``remaining`` counter carried ACROSS segment boundaries -- never
    reset per segment. This is deliberate, not incidental: clipping each
    segment against the row's remaining budget in order produces the
    IDENTICAL result ``_clip_cells`` would produce on the segments'
    concatenated string in one call (a strict left-to-right cell-budget
    walk is associative across a string split at any character boundary),
    so a later segment can never render past where the earlier segments'
    own combined width already used up the row, and a wide/CJK character
    straddling where the row's budget runs out is dropped whole rather than
    split -- same discipline ``_clip_cells`` itself already guarantees
    within one string. Each segment's text is sanitized (control chars ->
    plain space, alignment-preserving) BEFORE its own clip, same order as
    every other write here, so an embedded control character can't move
    the real cursor and escape whatever box this row sits in, and a
    CJK/fullwidth character is measured in display cells, not Python
    characters -- both hazards the module docstring documents in general
    the same way they apply to a single unsegmented line.

    Only the region's own FIRST content row is ever written -- this
    primitive draws exactly one line, unlike ``draw_lines``/
    ``draw_lines_attrs``, which fan a whole list of lines down the box.
    ``region is None`` or an empty ``segments`` sequence is a silent no-op,
    matching every sibling draw call's shape. A malformed individual
    segment (not a 2-tuple, or a non-``str`` text) is silently dropped --
    degrading that ONE run to nothing rather than raising or voiding the
    rest of the row, the same per-run tolerance ``draw_runs``'s own
    ``_coerce_run`` establishes for its per-run malformed-entry case."""
    if region is None or not segments:
        return
    y, x, w, h = region["y"], region["x"], region["w"], region["h"]
    if boxed:
        inner_y, inner_x, inner_w, inner_h = y + 1, x + 1, w - 2, h - 2
    else:
        inner_y, inner_x, inner_w, inner_h = y, x, w, h
    if inner_w < 1 or inner_h < 1:
        return
    cursor_x = inner_x
    remaining = inner_w
    for item in segments:
        if remaining <= 0:
            break
        try:
            text, attr = item
        except (TypeError, ValueError):
            continue
        if not isinstance(text, str):
            continue
        clipped = _clip_cells(_sanitize_controls(text), remaining)
        if not clipped:
            continue
        _safe_write(win, inner_y, cursor_x, clipped, attr)
        used = sum(_cell_width(ch) for ch in clipped)
        cursor_x += used
        remaining -= used


def draw_refuse_message(win: curses.window, message: str, attr: int) -> None:
    """``mode == "too_small"``: render the layout's refusal message and
    nothing else (no chrome glyphs, no panels) -- caller must ``erase()``
    first the same as any other draw pass."""
    _safe_write(win, 0, 0, message or "", attr)
