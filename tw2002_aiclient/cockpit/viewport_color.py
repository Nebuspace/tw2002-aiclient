"""pyte color-run -> curses-attr mapping for the GAME viewport (WO-P4-053
lane 1), split into two clearly separated halves:

1. Pure geometry (``align_color_runs`` / ``_clipped_run``) -- touches
   nothing curses-specific. Takes the FULL, untransformed color-run rows
   from ``tw2002_aiclient.session.terminal.TerminalScreen.color_map()``
   plus the ALREADY top-dropped/width-clipped text lines produced by
   ``cockpit.viewport.compose_viewport_lines`` (or an equivalent transform),
   and re-derives which color runs survive and where, ALIGNED to those
   exact surviving text rows/columns. This is the critical piece: the paint
   composer top-drops rows and clips columns independently of this module,
   and if the color runs are not put through the identical transform, a
   redraw silently paints the wrong cells -- a mis-tinted screen still
   *looks* authoritative, so getting this wrong is a silent, plausible
   corruption, not a crash. See ``align_color_runs``'s own docstring for
   exactly how alignment is derived without re-deriving width/height (and
   so can never drift out of sync with the composer's own transform) --
   and for its CALLER CONTRACT section: this function trusts
   ``color_rows`` is the full, untransformed map for the SAME capture as
   ``text_lines``; a same-length-but-wrong-capture color map cannot be
   detected from in here and must be ruled out one layer up, against the
   raw event, before either side is transformed.

2. curses-facing color resolution (``PYTE_TO_CURSES_COLOR`` / ``run_attr``)
   -- necessarily imports ``curses`` for its color constants; this is the
   acknowledged exception to "no curses import" the rest of this module
   avoids. The pair-ALLOCATION half of this (what used to be this module's
   own reference-implementation ``GameCellPairs``) now lives in
   ``screens.py``'s ``_SharedPairs`` -- widened to a ``(fg_name, bg_name)``
   cache key at the WO-P4-053 draw-seam merge -- so GAME-cell colors and
   chrome colors share the exact same process-lifetime pair allocator
   (curses color-PAIR NUMBERS are global to the whole terminal session; a
   second independent allocator here would reopen the Mack-flagged
   CRITICAL bug ``_SharedPairs`` exists to eliminate). ``run_attr`` below
   stays here, duck-typed against whatever allocator it's given.

Upstream contract (read ``tw2002_aiclient/session/terminal.py::color_map``
directly, this is a summary): each row is a list of run dicts ``{"start":
int, "end": int (EXCLUSIVE), "fg": str, "bg": str, "bold": bool}``,
run-length-encoded over the SAME bounding box as ``render_cropped()``.
``fg``/``bg`` are pyte color names: ``"red" "green" "brown" "blue"
"magenta" "cyan" "white" "black" "default"`` -- note ``"brown"``, pyte's
own name for what every real terminal renders as yellow; there is no
``"yellow"`` in pyte's vocabulary.

Hardening policy -- DELIBERATELY DIFFERENT from
``cockpit.viewport.compose_viewport_lines``'s own "one bad row voids the
WHOLE grid" policy for TEXT: here, malformed color data degrades PER ROW
or PER RUN to *uncolored*, never voiding the whole grid's color and never
raising. Text-row corruption compromises the grid's actual meaning (wrong
content in the wrong place), so viewport.py is right to treat it as
all-or-nothing; color is a decorative overlay on top of an ALREADY-valid
text grid, so losing color for one bad run or one bad row is the
proportionate, honest degrade -- "uncolored" is honest, a WRONG color
would be a lie, but voiding an entire otherwise-good screen's color over
one bad run would be needlessly destructive. A hostile dict/list subclass
whose own ``.get()``/``in``/iteration raises is out of contract, same as
every sibling composer (``cockpit.viewport``'s own module docstring states
this identically) -- the daemon's real wire payload is always a plain
``json.loads()`` object.

No ``curses`` import is needed by ``align_color_runs`` itself; it deals
only in the same plain dict/str/int shapes the rest of this codebase's
pure composers use.
"""

from __future__ import annotations

import curses

# pyte's color names (tw2002_aiclient/session/terminal.py's color_map()) ->
# curses' basic-8 constants. pyte calls ANSI code 33 "brown"; every real
# terminal renders it as yellow, so that's what it maps to here (mirrors
# archive precedent: archive/pre-rebirth-2026-07-23/code/twclient/
# spectate_app.py's own _PYTE_TO_CURSES_COLOR, same table). "default" is
# deliberately ABSENT from this dict -- it means "terminal default", not a
# color to force, and resolves to curses' -1 sentinel in
# ``_curses_color_of`` below, same as any other unrecognized name.
PYTE_TO_CURSES_COLOR: dict[str, int] = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "brown": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
}


def _curses_color_of(name: object) -> int:
    """pyte color name -> curses basic-8 int, or ``-1`` (terminal default,
    ``curses.use_default_colors()``'s sentinel) for ``"default"`` or any
    unrecognized/hostile ``name`` -- degrading an unknown name to "default"
    is the honest choice (never guess a color that was never named). Never
    raises regardless of ``name``'s type."""
    if not isinstance(name, str):
        return -1
    return PYTE_TO_CURSES_COLOR.get(name, -1)


# ---------------------------------------------------------------------------
# Pure geometry: aligning color runs to the composer's own top-drop/clip
# ---------------------------------------------------------------------------

_REQUIRED_RUN_KEYS = ("start", "end", "fg", "bg", "bold")


def _clipped_run(run: object, row_len: int) -> dict[str, object] | None:
    """Validate + column-clip ONE run dict against a row whose FINAL
    (already width-clipped) length is ``row_len``. Returns a new run dict
    with ``start``/``end`` clamped into ``[0, row_len)`` on success, or
    ``None`` when the run is malformed OR clips away to nothing (an
    ``end <= start`` after clamping means no surviving cells -- this single
    clip-then-check-emptiness path is what naturally handles both the
    NORMAL case (a legitimate run straddling the new width boundary
    truncates to its surviving prefix) and the MALFORMED case (a run
    entirely outside the row's real bounds clips down to empty and is
    dropped) with one piece of logic, not two.

    Malformed inputs that return ``None``: ``run`` not a ``dict``; any of
    ``start``/``end``/``fg``/``bg``/``bold`` missing; ``start``/``end`` not
    a plain ``int`` (``bool`` explicitly excluded -- it IS an ``int``
    subclass in Python but a boolean column index is nonsensical, same
    bool-exclusion precedent as ``cockpit.tones``'s ``_safe_fraction``);
    ``end <= start`` before clipping; ``fg``/``bg`` not a plain ``str``;
    ``bold`` not a plain ``bool``. Never raises."""
    if not isinstance(run, dict):
        return None
    if not all(k in run for k in _REQUIRED_RUN_KEYS):
        return None
    start, end = run["start"], run["end"]
    fg, bg, bold = run["fg"], run["bg"], run["bold"]
    if isinstance(start, bool) or not isinstance(start, int):
        return None
    if isinstance(end, bool) or not isinstance(end, int):
        return None
    if end <= start:
        return None
    if not isinstance(fg, str) or not isinstance(bg, str):
        return None
    if not isinstance(bold, bool):
        return None
    clipped_start = max(0, start)
    clipped_end = min(row_len, end)
    if clipped_start >= clipped_end:
        return None
    return {"start": clipped_start, "end": clipped_end, "fg": fg, "bg": bg, "bold": bold}


def align_color_runs(
    color_rows: object, text_lines: object
) -> list[list[dict[str, object]]]:
    """Align ``color_rows`` (the FULL, untransformed output of
    ``TerminalScreen.color_map()``) to ``text_lines`` (the ALREADY
    top-dropped/width-clipped output of ``compose_viewport_lines`` or an
    equivalent transform). Returns one run-list per entry of
    ``text_lines`` -- same length, same order -- so a caller can always
    ``zip(text_lines, align_color_runs(color_rows, text_lines))`` safely,
    even when ``color_rows`` itself is missing or malformed (that degrades
    every row to ``[]``, never changes the returned length).

    Row alignment is BOTTOM-anchored, deliberately: ``compose_viewport_lines``
    top-drops by keeping the LAST ``height`` rows (``rows[-height:]``) --
    this function reuses ``len(text_lines)`` (the row count that already
    survived that slice) instead of re-deriving ``height`` as a separate
    parameter, so the two can never drift out of sync. Concretely: with
    ``n = len(text_lines)``, if ``color_rows`` has at least ``n`` rows, the
    LAST ``n`` of them are selected (``color_rows[-n:]``) -- the same rows
    ``compose_viewport_lines`` kept. If ``color_rows`` has FEWER than ``n``
    rows (hostile/out-of-sync input), the missing LEADING rows degrade to
    ``[]`` (uncolored) rather than misaligning the ones that do exist.

    Column clipping uses each row's OWN final length (``len(text_lines[i])``),
    not a separately-passed width -- ``compose_viewport_lines`` clips every
    row to the same nominal width via ``row[:width]``, which is a no-op for
    a row that was already shorter, so ``len(text_lines[i])`` already IS
    ``min(width, original_row_length)`` for that row; deriving the clip
    bound from the actual surviving text avoids a second width parameter
    that could silently disagree with it.

    CALLER CONTRACT -- this function trusts that ``color_rows`` is the
    FULL, untransformed ``color_map()`` output for the exact SAME capture
    as ``text_lines`` (i.e. ``len(color_rows)`` equals the original,
    pre-top-drop screen row count the text was itself sliced from). The
    bottom-anchored ``color_rows[-n:]`` slice above is only correct under
    that assumption -- it has no way to independently learn the true
    original row count from ``text_lines`` alone, since top-dropped text
    and an under-count color map are indistinguishable from in here (e.g.
    a screen with a genuinely shorter color map than the raw event's
    ``screen`` -- 28 color rows for a 30-row screen -- silently slices the
    WRONG 25 color rows against the surviving 25 text rows: no crash, no
    empty result, every row's color just off by two). This function
    degrades ``color_rows`` being absent, non-list, or *shorter than*
    ``text_lines`` (see above) but cannot detect this "same length, wrong
    capture" case at all -- that check belongs one layer up, against the
    RAW event, before either side is transformed: verify
    ``len(event["color"]) == len(event["screen"])`` and drop color
    entirely (not this function, the caller) on any mismatch. Uncolored is
    honest; a same-length-but-misaligned color map is a lie that still
    looks authoritative, same principle as every other hardening choice in
    this module.

    Per-row/per-run hardening (module docstring has the "why uncolored, not
    void-the-grid" rationale): ``text_lines`` not a ``list``/``tuple`` ->
    ``[]`` (nothing to align to). ``color_rows`` not a ``list``/``tuple`` ->
    every row degrades to ``[]``. A row of ``color_rows`` that isn't itself
    a ``list``/``tuple`` -> that one row's runs become ``[]``. A row of
    ``text_lines`` that isn't a ``str`` -> treated as zero-length (every run
    for that row clips away to nothing). Any individual malformed run (see
    ``_clipped_run``) is dropped, not fatal to its row. Never raises."""
    if not isinstance(text_lines, (list, tuple)):
        return []
    n = len(text_lines)
    if n == 0:
        return []

    if isinstance(color_rows, (list, tuple)):
        color_rows = list(color_rows)
    else:
        color_rows = []

    if len(color_rows) >= n:
        selected = color_rows[len(color_rows) - n :]
    else:
        selected = [[] for _ in range(n - len(color_rows))] + color_rows

    out: list[list[dict[str, object]]] = []
    for i in range(n):
        row_text = text_lines[i]
        row_len = len(row_text) if isinstance(row_text, str) else 0
        raw_row = selected[i]
        if not isinstance(raw_row, (list, tuple)):
            out.append([])
            continue
        row_out = []
        for run in raw_row:
            clipped = _clipped_run(run, row_len)
            if clipped is not None:
                row_out.append(clipped)
        out.append(row_out)
    return out


# ---------------------------------------------------------------------------
# curses-facing color resolution + pair allocation
# ---------------------------------------------------------------------------


def run_attr(pairs: object, run: object) -> int:
    """Resolve ONE aligned run dict (as returned by ``align_color_runs``)
    to a final curses attr: ``pairs.attr_for(fg, bg)``'s base color attr |
    ``curses.A_BOLD`` when the run's own ``"bold"`` is ``True``.

    ``pairs`` is duck-typed against any object exposing
    ``attr_for(fg_name, bg_name) -> int`` -- in production that's
    ``screens.py``'s process-lifetime ``_shared_pairs`` (a ``_SharedPairs``
    instance, widened at the WO-P4-053 draw-seam merge from a bare
    ``str`` color-name cache key to ``(fg_name, bg_name)`` so GAME cells
    and chrome share the one allocator curses color-PAIR numbers require;
    see that class's own docstring). This module takes no dependency on
    ``screens.py`` itself, so tests here pass any object with a matching
    ``attr_for`` instead. The allocator returns a base (non-bold) attr,
    the caller ORs bold in, never the allocator itself -- mirrors
    ``screens.py``'s own ``_shared_pairs.attr_for(name) | curses.A_BOLD``
    convention used by every chrome caller. Defends independently of
    ``align_color_runs`` (a caller could hand this a raw, un-aligned run):
    anything not shaped like ``{"fg": str, "bg": str, "bold": bool}``
    degrades to ``curses.A_NORMAL`` rather than raising."""
    if not isinstance(run, dict):
        return curses.A_NORMAL
    attr = pairs.attr_for(run.get("fg"), run.get("bg"))
    if run.get("bold") is True:
        attr |= curses.A_BOLD
    return attr
