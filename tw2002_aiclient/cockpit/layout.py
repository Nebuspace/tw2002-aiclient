"""Pure geometry for the trainer-cockpit frame (PWO-031/033,
``workorders/WO-P3-030-033-cockpit-frame-PREP.md``).

No ``curses`` import here on purpose — ``frame_layout()`` takes a terminal's
current ``(lines, cols)`` and returns a plain regions dict; drawing those
regions with real ``curses`` windows is a later WO. This mirrors
``tw2002_aiclient/cockpit/strip.py``'s no-curses discipline and ports the
archived ``twclient/spectate_layout.py::frame_layout`` reflow ladder, scoped
down to what PWO-031/033 (+ PWO-034's GOALS/PRIORITIES stack) need: the
outer frame, the row-1 character/profile strip band (PWO-032), the
three-column body (left gutter, itself stacked GOALS above PRIORITIES |
center game viewport | right gutter, itself stacked HUD above DECISIONS
per PWO-036), and the bottom LOGS band. The archived function's
MENU MAP/FORMATIONS/chain-bubble/control/intervention sub-regions belong to
later WOs (mode-line, Phase 5) and are deliberately not ported here — see
the module docstring on ``frame_layout`` for the DOCS-WIN fold-floor
correction this module encodes.
"""

from __future__ import annotations

# -- Canon constants (canon/surfaces/visual-language.md "Responsive-fold
# ladder" + "Box-drawing hierarchy") -- the target contract for this port.
#
# VIEWPORT_H is 27, not 26: the bordered viewport wraps the daemon's true
# native pyte grid, which is 80x25 (``session/terminal.py``'s
# ``Terminal(columns=80, lines=25)``), one border cell on every side, zero
# inset -- so the bordered box itself needs 25 + 2 = 27 rows. The prior 26
# was cockpit drift (an 80x24 assumption baked in before this port checked
# the daemon's own terminal dims); the engine's 80x25 was always right, so
# the cockpit grows to match it rather than the engine shrinking.
VIEWPORT_W, VIEWPORT_H = 82, 27
# Native content the bordered viewport wraps, zero inner padding on every
# side (visual-language.md: "Viewport zero-inset is an invariant").
GAME_W, GAME_H = VIEWPORT_W - 2, VIEWPORT_H - 2  # 80 x 25

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

# CONTROL_STRIP (WO-P3-038): a single bare content row, the bottom-most
# interior row of the frame, below LOGS (canon `trainer-aiclient` mock,
# `trainer-cockpit.md` ~line 46 -- "«control strip — mode badge · → TX ·
# A/R/T · run/record/panic» (owned by mode-line-and-teach-controls — see N5
# boundary)"). This WO renders only the row and its liveness cluster; the
# mode badge / A/R/T keys / run-record-panic cluster belong to the N5 WO.
CONTROL_STRIP_H = 1

# GOALS box height (PWO-034): the authored line set is nine strategic
# prerequisites -- Turns, Credits, StarDock, Map, Formations, Chain, Ship
# prices, Hold price, Fighters (canon `trainer-cockpit.md` "Left gutter"
# GOALS bullet) -- plus its own top/bottom border. GOALS stacks *above*
# PRIORITIES in the left gutter (was the sole occupant pre-PWO-034); GOALS
# claims this height first and PRIORITIES gets whatever vertical room is
# left, shrinking or dropping entirely rather than the two panels
# overlapping or GOALS itself ever rendering short of its own floor when
# any room exists at all.
GOALS_CONTENT_H = 9
GOALS_BOX_MIN_H = GOALS_CONTENT_H + 2

# HUD box height (PWO-036): the right gutter mirrors the left gutter's
# stacked-panel shape — HUD stacks *above* DECISIONS (was the sole occupant
# pre-PWO-036). Right-gutter prose calls HUD "the always-on live read" that
# comes first in the gutter, and DECISIONS second (canon
# `trainer-cockpit.md` "Right gutter" ~77-84) -- HUD is the priority
# claimant here the same way GOALS is on the left: it claims its own
# height floor first, DECISIONS gets whatever remains, shrinking or
# dropping entirely rather than the two panels overlapping.
#
# HUD_CONTENT_H is grounded in the HUD's own cited cell inventory, not a
# guess: canon's HUD section names five fixed-order fields --
# CREDITS/SECTOR/TURNS/CARGO/PROFIT -- and states "SECTOR/TURNS/CARGO/
# PROFIT follow in a uniform 2-row cell stride" (`trainer-cockpit.md`
# "Spacing, alignment & hierarchy" ~306-310). The archived renderer this
# doc cites (`spectate_app.py::_draw_hud_gutter`, ~1320-1344) confirms the
# stride is uniform across all five cells, CREDITS included -- its extra
# delta-chip/sparkline decorations render INLINE on the same two rows
# (chip appended to the value row, sparkline appended to the freshness
# row), not as additional rows. 5 cells x 2-row stride = 10 content rows;
# PWO-037 (HUD freshness markers) is what actually fills these rows --
# this WO reserves the geometry those cells need so the DECISIONS split
# below never has to reflow again once 037 lands, the same forward-looking
# spirit as GOALS_CONTENT_H reserving its own line count ahead of
# state_parser wiring.
HUD_CONTENT_H = 10
HUD_BOX_MIN_H = HUD_CONTENT_H + 2


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
    band), ``goals``/``left_gutter``/``center``/``right_gutter``/``decisions``
    (the three-column body — each present only where its tier draws it; the
    left gutter itself is stacked GOALS above PRIORITIES per PWO-034, see
    ``GOALS_BOX_MIN_H``; the right gutter itself is stacked HUD above
    DECISIONS per PWO-036, see ``HUD_BOX_MIN_H`` — ``right_gutter`` is the
    HUD sub-region, unchanged key, ``decisions`` is the new sub-region below
    it), ``logs`` (the bottom full-width band), ``control_strip`` (WO-P3-038
    — the single bare row below ``logs``, the frame's own last interior row;
    see ``CONTROL_STRIP_H``). Every region is clamped to at least 1x1 and
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
            "goals": None,
            "left_gutter": None,
            "center": None,
            "right_gutter": None,
            "decisions": None,
            "logs": None,
            "control_strip": None,
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
    logs_h_actual = rest_h - column_h  # LOGS' own height -- untouched by the CONTROL_STRIP carve below

    # CONTROL_STRIP (WO-P3-038) claims its single row LAST, out of the
    # COLUMN band's own slot only -- never LOGS'. `logs_h_actual` above is
    # computed with the exact same expression this module used before this
    # row existed, so LOGS never shrinks below its existing floor because of
    # this addition (the "logs must never shrink" invariant holds by
    # construction, not by a runtime check). It only carves into `column_h`,
    # which already clamps to >=1 and — per the "leftover slot height...
    # deliberately left unclaimed" note below — typically carries several
    # rows of slack past `VIEWPORT_H` at real terminal sizes, so this rarely
    # visibly shrinks GOALS/center/HUD either. `control_strip` drops to
    # absent (``None``) rather than ever pulling the column band below its
    # own >=1-row floor -- "control_strip drops first" under height
    # pressure, never LOGS or the column body.
    #
    # Present/absent is decided purely by this height arithmetic,
    # independent of the column's fold `mode` -- deliberately so: like
    # `strip`/`logs`, CONTROL_STRIP is a full-width band, not a gutter-tied
    # instrument box, so it renders the same whether or not a side gutter or
    # the viewport border is present (`no_border` tier included). Under the
    # real MIN_LINES=20 floor, `column_h` here is always > 1 before this
    # carve runs (rest_h >= 17, logs_h == LOGS_MIN_H == 3, so
    # column_h >= 14) — CONTROL_STRIP is therefore present at every
    # reachable non-``too_small`` size today; the `None` branch is a latent
    # guard, same shape as `LOGS_MIN_H`'s own clamp above, for a future
    # floor change.
    if column_h > 1:
        control_strip_h = 1
        column_h -= 1
    else:
        control_strip_h = 0

    logs = {"y": rest_y + column_h, "x": ox, "w": i_cols, "h": logs_h_actual}
    control_strip = (
        {"y": rest_y + column_h + logs_h_actual, "x": ox, "w": i_cols, "h": control_strip_h}
        if control_strip_h > 0
        else None
    )

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
    #
    # The left gutter's ``center_h``-tall slot is itself stacked (PWO-034):
    # GOALS claims up to ``GOALS_BOX_MIN_H`` off the top first, PRIORITIES
    # gets whatever remains below it. GOALS is present at 1x1-or-taller
    # whenever the slot exists at all (``pri_w > 0``) — never dropped in
    # favor of PRIORITIES; PRIORITIES is what shrinks, then drops (``None``)
    # once GOALS alone has consumed the whole slot. Same width for both
    # (stacked, not side-by-side), so every existing PRIORITIES_W /
    # PRIORITIES_MIN_W tier width stays unchanged.
    goals = None
    left_gutter = None
    if pri_w > 0:
        goals_h = min(GOALS_BOX_MIN_H, center_h)
        goals = {"y": rest_y, "x": ox, "w": pri_w, "h": goals_h}
        pri_h = center_h - goals_h
        if pri_h > 0:
            left_gutter = {"y": rest_y + goals_h, "x": ox, "w": pri_w, "h": pri_h}

    # The right gutter's ``center_h``-tall slot is itself stacked (PWO-036),
    # mirroring the left gutter's GOALS-over-PRIORITIES split above: HUD
    # claims up to ``HUD_BOX_MIN_H`` off the top first (right-gutter prose
    # names HUD "the always-on live read" that comes first --
    # `trainer-cockpit.md` "Right gutter" ~77-84 -- so it wins height
    # contention the same way GOALS does on the left), DECISIONS gets
    # whatever remains below it. HUD is present at 1x1-or-taller whenever
    # the right gutter exists at all (``has_right_gutter``) — never dropped
    # in favor of DECISIONS; DECISIONS is what shrinks, then drops
    # (``None``) once HUD alone has consumed the whole slot. ``right_gutter``
    # keeps its pre-PWO-036 key (it was the sole occupant, now it's the HUD
    # sub-region) so ``screens.py``'s existing HUD draw call needs no key
    # rename — same "reuse the existing key for the top-priority occupant"
    # shape as ``left_gutter`` staying FOCUS's key after PWO-034.
    #
    # NOTE for the future Phase-5 intervention/STOP strip (frame PREP
    # geometry guard #6): that strip claims height FIRST, ahead of every
    # other region, when it lands -- this stacked-gutter shape does not
    # preclude that; the strip's own floor will be carved out of ``rest_h``
    # before this column split runs, same as LOGS is today.
    right_gutter = None
    decisions = None
    if has_right_gutter:
        hud_h = min(HUD_BOX_MIN_H, center_h)
        right_gutter = {
            "y": rest_y,
            "x": ox + i_cols - HUD_GUTTER_W,
            "w": HUD_GUTTER_W,
            "h": hud_h,
        }
        dec_h = center_h - hud_h
        if dec_h > 0:
            decisions = {
                "y": rest_y + hud_h,
                "x": ox + i_cols - HUD_GUTTER_W,
                "w": HUD_GUTTER_W,
                "h": dec_h,
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
        "goals": goals,
        "left_gutter": left_gutter,
        "center": center,
        "right_gutter": right_gutter,
        "decisions": decisions,
        "logs": logs,
        "control_strip": control_strip,
    }
