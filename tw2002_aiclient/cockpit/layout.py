"""Pure geometry for the trainer-cockpit frame (PWO-031/033,
``workorders/WO-P3-030-033-cockpit-frame-PREP.md``).

No ``curses`` import here on purpose — ``frame_layout()`` takes a terminal's
current ``(lines, cols)`` and returns a plain regions dict; drawing those
regions with real ``curses`` windows is a later WO. This mirrors
``tw2002_aiclient/cockpit/strip.py``'s no-curses discipline and ports the
archived ``twclient/spectate_layout.py::frame_layout`` reflow ladder, scoped
down to what PWO-031/033 need: the outer frame, the row-1 character/profile
strip band (PWO-032), the three-column body (left PRIORITIES gutter | center
game viewport | right HUD gutter), and the bottom LOGS band. The archived
function's PRIORITIES/MENU MAP/FORMATIONS/DECISIONS/chain-bubble/control/
intervention sub-regions belong to later WOs (mode-line, Phase 5) and are
deliberately not ported here — see the module docstring on ``frame_layout``
for the DOCS-WIN fold-floor correction this module encodes.
"""

from __future__ import annotations

# -- Canon constants (canon/surfaces/visual-language.md "Responsive-fold
# ladder" + "Box-drawing hierarchy") -- the target contract for this port.
VIEWPORT_W, VIEWPORT_H = 82, 26
# Native content the bordered viewport wraps, zero inner padding on every
# side (visual-language.md: "Viewport zero-inset is an invariant").
GAME_W, GAME_H = VIEWPORT_W - 2, VIEWPORT_H - 2  # 80 x 24

HUD_GUTTER_W = 36
PRIORITIES_W = HUD_GUTTER_W  # the left PRIORITIES gutter mirrors HUD width at the full tier
PRIORITIES_MIN_W = 20

# Fold-ladder floors, named to match the archived module so the numbers are
# traceable back to the same VIEWPORT_W/HUD_GUTTER_W/PRIORITIES_W arithmetic
# canon cites. `[DOCS-WIN]` the archived frame_layout's own docstring stated
# the "full" floor as the stale ">=142"; visual-language.md self-flags this
# and states the constant-derived value is 154 — that fix is applied both
# here and in canon (visual-language.md, this port's D4).
MINIMAL_HEADER_MIN_COLS = VIEWPORT_W  # 82 -- bordered viewport alone floor
RIGHT_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W  # 118 -- viewport + right HUD, zero-margin fit
LEFT_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_MIN_W  # 138 -- narrowed left gutter also fits
FULL_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_W  # 154 -- both gutters at full width

MIN_COLS = 60
MIN_LINES = 20

# One-cell outer frame around the whole client (PWO-031). Layout math below
# uses the INNER content size (cols/lines minus 2); the floors above are
# already content floors — the MIN_COLS/MIN_LINES too-small gate is the one
# comparison made against the raw terminal size, matching the archived
# precedent (a raw-cols floor, not an inner-cols one).
OUTER_FRAME_PAD = 1  # per side

# Row 1 inside the frame is always the character/profile strip (PWO-032) --
# unlike the archived module's optional header row, this band never folds
# away; it truncates to line-tail at the minimal tier instead (canon:
# "the strip truncates to line-tail at minimal tier, never wraps/h-scrolls").
STRIP_H = 1

# The bottom LOGS band's minimum height (border + one content row + border).
# Canon does not yet cite an exact LOGS-band number at this reduced scope
# (that arithmetic — LOG_BOX_MIN_H/BAND_H_MAX/DECISIONS split — belongs to
# the archived module's much larger HUD/DECISIONS/chain apparatus, out of
# PWO-031/033's scope per the PREP). LOGS_MIN_H is this port's own minimal,
# review-worthy floor, not a canon-cited constant.
LOGS_MIN_H = 3


def frame_layout(lines: int, cols: int) -> dict:
    """Pure reflow: given the terminal's current ``(lines, cols)``, decide
    which cockpit-frame regions fit and return them as a plain dict —
    ``{"y", "x", "w", "h"}`` per region, no curses/terminal involved.

    Ladder (inner-cols-driven, PRIORITIES_MIN_W/HUD_GUTTER_W of headroom
    shed first, the center viewport surviving last — visual-language.md
    "Responsive-fold ladder"):
      >=154  "full"          -- left PRIORITIES (36) | centered game | right HUD (36)
      >=138  "right_gutter"  -- bordered viewport (left-anchored) + right HUD;
                                a narrowed left PRIORITIES (20) still fits
      >=118  "right_gutter"  -- bordered viewport + right HUD only, no left gutter
      >=82   "minimal"       -- bordered viewport, centered, no side gutter
      >=60   "no_border"     -- viewport border dropped, game full-bleed/clipped
      else   "too_small"     -- refuse to render (message states the floor)

    The two ">=138"/">=118" rows share the "right_gutter" mode string (the
    archived module's own convention — the fold within that mode is whether
    ``left_gutter`` is present, not a distinct mode name).

    Regions returned: ``mode``, ``message`` (only set at ``too_small``),
    ``outer`` (the whole client), ``strip`` (row 1, the character/profile
    band), ``left_gutter``/``center``/``right_gutter`` (the three-column
    body — each present only where its tier draws it), ``logs`` (the
    bottom full-width band). Every region is clamped to at least 1x1 and
    stays inside ``outer``; siblings never overlap.
    """
    if lines < MIN_LINES or cols < MIN_COLS:
        return {
            "mode": "too_small",
            # "×" is a canon-cited literal (visual-language.md:208,
            # trainer-cockpit.md:368) — same no-swap family as "·"/"—"
            # (never degrades to an ASCII "x" twin, even under TW2002_ASCII=1).
            "message": (
                f"Terminal too small ({cols}×{lines}) — need at least "
                f"{MIN_COLS}×{MIN_LINES}. Resize to continue."
            ),
            "outer": None,
            "strip": None,
            "left_gutter": None,
            "center": None,
            "right_gutter": None,
            "logs": None,
        }

    outer = {"y": 0, "x": 0, "w": cols, "h": lines}
    ox = oy = OUTER_FRAME_PAD
    i_cols = cols - 2 * OUTER_FRAME_PAD
    i_lines = lines - 2 * OUTER_FRAME_PAD

    strip = {"y": oy, "x": ox, "w": i_cols, "h": STRIP_H}

    rest_y = oy + STRIP_H
    rest_h = max(1, i_lines - STRIP_H)

    # LOGS claims its minimum floor first (never less than 1 row even when
    # the terminal is barely past MIN_LINES); the column band above it gets
    # whatever remains.
    #
    # The `max(1, rest_h - 1)` half of this clamp is unreachable under the
    # current MIN_LINES=20 (rest_h >= 17 for anything past too_small, so
    # logs_h is always exactly LOGS_MIN_H) — it's a latent guard that only
    # activates if MIN_LINES is ever lowered enough to shrink rest_h below
    # 2; a future floor change should revisit this arithmetic deliberately.
    logs_h = min(LOGS_MIN_H, max(1, rest_h - 1))
    column_h = max(1, rest_h - logs_h)
    logs = {"y": rest_y + column_h, "x": ox, "w": i_cols, "h": rest_h - column_h}

    if i_cols >= FULL_GUTTER_MIN_COLS:
        mode = "full"
        pri_w = PRIORITIES_W
    elif i_cols >= LEFT_GUTTER_MIN_COLS:
        mode = "right_gutter"
        pri_w = PRIORITIES_MIN_W
    elif i_cols >= RIGHT_GUTTER_MIN_COLS:
        mode = "right_gutter"
        pri_w = 0
    elif i_cols >= MINIMAL_HEADER_MIN_COLS:
        mode = "minimal"
        pri_w = 0
    else:
        mode = "no_border"
        pri_w = 0

    has_right_gutter = mode in ("full", "right_gutter")
    border = mode != "no_border"

    center_w = VIEWPORT_W if border else min(GAME_W, i_cols)
    center_h = min(VIEWPORT_H, column_h) if border else min(GAME_H, column_h)

    # Gutters mirror the center viewport's height, not the whole column
    # slot (``column_h``, which can run taller than VIEWPORT_H on a
    # generously tall terminal) — matching the archived module's "PRIORITIES
    # keeps full viewport height" precedent. Any leftover slot height below
    # the gutters is deliberately left unclaimed here (out of this WO's
    # scope; the archived module hands it to MENU MAP/FORMATIONS/DECISIONS
    # sub-panels a later WO will port), rather than silently reassigning it
    # to LOGS.
    left_gutter = None
    if pri_w > 0:
        left_gutter = {"y": rest_y, "x": ox, "w": pri_w, "h": center_h}

    right_gutter = None
    if has_right_gutter:
        right_gutter = {
            "y": rest_y,
            "x": ox + i_cols - HUD_GUTTER_W,
            "w": HUD_GUTTER_W,
            "h": center_h,
        }

    if mode == "full":
        left_edge = ox + pri_w
        right_edge = ox + i_cols - HUD_GUTTER_W
        middle = right_edge - left_edge
        center_x = left_edge + max(0, (middle - center_w) // 2)
    elif mode == "right_gutter":
        center_x = ox + pri_w  # left-anchored after the (possibly-absent) left gutter
    elif mode == "minimal":
        center_x = ox + max(0, (i_cols - center_w) // 2)
    else:  # no_border
        center_x = ox

    center = {"y": rest_y, "x": center_x, "w": center_w, "h": center_h, "border": border}

    return {
        "mode": mode,
        "message": None,
        "outer": outer,
        "strip": strip,
        "left_gutter": left_gutter,
        "center": center,
        "right_gutter": right_gutter,
        "logs": logs,
    }
