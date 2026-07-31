"""Pure geometry for the trainer-cockpit frame (PWO-031/033,
``workorders/WO-P3-030-033-cockpit-frame-PREP.md``).

No ``curses`` import here on purpose — ``frame_layout()`` takes a terminal's
current ``(lines, cols)`` and returns a plain regions dict; drawing those
regions with real ``curses`` windows is a later WO. This mirrors
``tw2002_aiclient/cockpit/strip.py``'s no-curses discipline and ports the
archived ``twclient/spectate_layout.py::frame_layout`` reflow ladder, scoped
down to what PWO-031/033 (+ PWO-034's GOALS/PRIORITIES stack) need: the
outer frame, the row-1 character/profile strip band (PWO-032), the
three-column body (left gutter, itself stacked GOALS -- with FOCUS nested
inside it, WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS -- above a tall FORMATIONS
panel | center game viewport | right gutter, itself stacked HUD above
DECISIONS per PWO-036), the bottom LOGS band, and — only while a halt is
actually reported — the intervention/STOP banner (WO-P5-064, see
``INTERVENTION_H``), and — when five wholly spare rows exist under a
full bordered 80×25 viewport — the always-on chain-bubble strip
(WO-PLAY-CHAIN-BUBBLE-VIZ). MENU MAP remains a later WO.
See the module docstring on ``frame_layout`` for the DOCS-WIN fold-floor
correction this module encodes.
"""

from __future__ import annotations

# The banner's height is defined ONCE, by the composer that fills it --
# imported here as an alias rather than re-spelled as a second literal, so
# the region's height and the composer's band count cannot drift apart
# (the same "one shared source, not two hand-kept-in-sync copies"
# discipline ``cockpit.control_seat``'s own ``_compose_segments`` uses for
# its two public composers). This is the only import this otherwise
# dependency-free geometry module takes; ``cockpit.stopbanner`` is itself
# pure and curses-free, so the no-``curses`` discipline above is intact.
from .stopbanner import BANNER_H as INTERVENTION_H

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
# Always-on best-chain bubbles under the viewport (WO-PLAY-CHAIN-BUBBLE-VIZ).
# Never carve these out of VIEWPORT_H — fold the region instead.
CHAIN_VIZ_H = 5

# Wider side gutters (Max 2026-07-31): Goals⊃Focus + Formations (left) and
# HUD + Decisions (right) claim more horizontal room than the archive's 36.
HUD_GUTTER_W = 44
PRIORITIES_W = HUD_GUTTER_W  # the left PRIORITIES gutter mirrors HUD width at the full tier
PRIORITIES_MIN_W = 20

# Fold-ladder floors, named to match the archived module so the numbers are
# traceable back to the same VIEWPORT_W/HUD_GUTTER_W/PRIORITIES_W arithmetic
# canon cites. `[DOCS-WIN]` the archived frame_layout's own docstring stated
# the "full" floor as the stale ">=142"; visual-language.md self-flags this
# and states the constant-derived value (now 170 = 82+44+44) — that fix is
# applied both here and in canon (visual-language.md, this port's D4).
MINIMAL_HEADER_MIN_COLS = VIEWPORT_W  # 82 -- bordered viewport alone floor
RIGHT_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W  # 126 -- viewport + right HUD, zero-margin fit
LEFT_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_MIN_W  # 146 -- narrowed left gutter also fits
FULL_GUTTER_MIN_COLS = VIEWPORT_W + HUD_GUTTER_W + PRIORITIES_W  # 170 -- both gutters at full width

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
# GOALS bullet) -- plus its own top/bottom border.
GOALS_CONTENT_H = 9

# FOCUS is nested INSIDE the GOALS box (WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS,
# DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 5: "Left
# gutter: GOALS outer box with FOCUS nested inside") rather than a sibling
# stacked below it, as it was pre-this-WO. FOCUS_CONTENT_H reserves room for
# its own ranked list the same way GOALS_CONTENT_H reserves its own digest --
# canon's three named FOCUS candidate kinds (Trade chain / Upgrade / Explore,
# `canon/engine/priority-engine.md` "Layer 2 -- FOCUS") ground the count.
# FOCUS_NESTED_BOX_H adds the nested sub-box's OWN top/bottom border (see
# ``nested_focus_region`` below, which computes its actual on-screen rect).
FOCUS_CONTENT_H = 3
FOCUS_NESTED_BOX_H = FOCUS_CONTENT_H + 2

# GOALS_BOX_MIN_H is the OUTER Goals box's own height floor: its own
# top/bottom border, the GOALS_CONTENT_H digest, AND the nested FOCUS
# sub-box (FOCUS_NESTED_BOX_H) entirely inside it -- box-in-box, not two
# stacked siblings each paying for their own outer border. GOALS claims this
# height first (clamped to whatever the column actually has -- see
# ``frame_layout``'s own pri_w block); FORMATIONS gets whatever vertical
# room is left below it, shrinking or dropping entirely rather than the two
# panels overlapping or GOALS itself ever rendering short of its own floor
# when any room exists at all.
GOALS_BOX_MIN_H = 2 + GOALS_CONTENT_H + FOCUS_NESTED_BOX_H

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


def frame_layout(lines: int, cols: int, *, needs_attention: bool = False) -> dict:
    """Pure reflow: given the terminal's current ``(lines, cols)``, decide
    which cockpit-frame regions fit and return them as a plain dict —
    ``{"y", "x", "w", "h"}`` per region, no curses/terminal involved.

    Ladder (inner-cols-driven, PRIORITIES_MIN_W/HUD_GUTTER_W of headroom
    shed first, the center viewport surviving last — visual-language.md
    "Responsive-fold ladder"):
      >=170  "full"          -- left PRIORITIES (44) | centered game | right HUD (44)
      >=146  "right_gutter"  -- bordered viewport (left-anchored) + right HUD;
                                a narrowed left PRIORITIES (20) still fits
      >=126  "right_gutter"  -- bordered viewport + right HUD only, no left gutter
      >=82   "minimal"       -- bordered viewport, centered, no side gutter
      >=60   "no_border"     -- viewport border dropped, game full-bleed/clipped
      else   "too_small"     -- refuse to render (message states the floor)

    The two ">=146"/">=126" rows share the "right_gutter" mode string (the
    archived module's own convention — the fold within that mode is whether
    ``left_gutter`` is present, not a distinct mode name).

    ``needs_attention`` (WO-P5-064) is the ONE piece of live daemon state
    this otherwise size-only function takes: ``True`` while the daemon
    reports a raised escalation (``cockpit.stopbanner.needs_attention``'s
    own reading of ``status["intervention"]``). It is keyword-only and
    defaults ``False``, so every pre-WO-P5-064 caller gets a
    byte-identical result and the ``intervention`` region below stays
    ``None`` — the banner is opt-in, never reserved-but-blank space.
    Mirrors the archived ``spectate_layout.frame_layout``'s own
    ``needs_attention`` parameter.

    Regions returned: ``mode``, ``message`` (only set at ``too_small``),
    ``outer`` (the whole client), ``strip`` (row 1, the character/profile
    band), ``goals``/``left_gutter``/``center``/``right_gutter``/``decisions``
    (the three-column body — each present only where its tier draws it; the
    left gutter itself is stacked GOALS (with FOCUS nested INSIDE the
    ``goals`` rect, box-in-box — see ``GOALS_BOX_MIN_H`` and the module-level
    ``nested_focus_region`` helper, WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS)
    above a tall FORMATIONS panel; the right gutter itself is stacked HUD
    above DECISIONS per PWO-036, see ``HUD_BOX_MIN_H`` — ``right_gutter`` is
    the HUD sub-region, unchanged key, ``decisions`` is the new sub-region
    below it), ``logs`` (the bottom full-width band), ``intervention``
    (WO-P5-064 — the STOP banner, present only while ``needs_attention``; see
    ``INTERVENTION_H``), ``control_strip`` (WO-P3-038 — the single bare row
    below them both, the frame's own last interior row; see
    ``CONTROL_STRIP_H``). Every region is clamped to at least 1x1 and
    stays inside ``outer``; siblings never overlap. ``left_gutter`` was
    FOCUS's key pre-WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS; it is now
    FORMATIONS' — FOCUS's own nested rect is NOT one of these top-level
    siblings (it deliberately overlaps ``goals``, its own outer box) and is
    computed separately by ``nested_focus_region(goals)``.
    """
    if lines < MIN_LINES or cols < MIN_COLS:
        return {
            "mode": "too_small",
            # "×" is a canon-cited literal (visual-language.md §"Glyph / status-marker vocabulary",
            # trainer-cockpit.md §"Empty / loading / cold-join / error / off-map states — concretely") — same no-swap family as "·"/"—"
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
            "chain": None,
            "right_gutter": None,
            "decisions": None,
            "logs": None,
            "intervention": None,
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
    logs_h_actual = rest_h - column_h  # LOGS' own height -- untouched by the INTERVENTION/CONTROL_STRIP carves below

    # CONTROL_STRIP (WO-P3-038) claims its single row LAST -- after the
    # INTERVENTION banner (WO-P5-064) below, which deliberately outranks
    # it -- out of the COLUMN band's own slot only, never LOGS'.
    # `logs_h_actual` above is computed with the exact same expression
    # this module used before this
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
    # carve runs (rest_h >= 17, logs_h == LOGS_MIN_H == 3, so column_h >=
    # 14, and >= 11 even after the INTERVENTION banner has taken its own
    # rows at a halt) — CONTROL_STRIP is therefore present at every
    # reachable non-``too_small`` size today; the `None` branch is a latent
    # guard, same shape as `LOGS_MIN_H`'s own clamp above, for a future
    # floor change.

    # INTERVENTION/STOP banner (WO-P5-064). Claims its rows BEFORE the
    # control strip below and NEVER out of LOGS' own slot -- canon's
    # safety-legibility invariant (`mode-line-and-teach-controls.md`: the
    # strip "claims leftover height first -- before the control strip,
    # before the ticker -- so a halt always surfaces even as the terminal
    # shrinks"; frame PREP geometry guard #6 states the same order,
    # naming the control strip and ticker specifically). Under height
    # pressure the control strip is what yields (`control_strip_h` falls
    # to 0 below), never this banner and never LOGS.
    #
    # [DOCS-WIN correction to this module's own prior forecast] The NOTE
    # that used to sit in the right-gutter block below predicted this
    # strip would carve out of `rest_h` "ahead of every other region,
    # ... same as LOGS is today" -- i.e. ahead of LOGS too. That would
    # shrink LOGS below its own floor at tight sizes, which is exactly
    # what the PREP's guard #6 does NOT ask for (it orders the banner
    # ahead of the control strip and ticker, not ahead of LOGS) and what
    # this module's own CONTROL_STRIP comment above establishes as an
    # invariant. So the banner carves from `column_h`, after
    # `logs_h_actual` is already fixed: LOGS' height is computed by the
    # identical expression whether or not a halt is raised, so "LOGS
    # never shrinks for the banner" holds by construction, not by a
    # runtime check.
    #
    # What it DOES cost, stated plainly rather than absorbed silently:
    # the rows come out of the column band, which the centre viewport and
    # both gutters size themselves from (`center_h = min(VIEWPORT_H,
    # column_h)`). At >= 37 lines the band still carries enough slack for
    # the viewport's full VIEWPORT_H, so the banner is free; below that
    # the viewport is already clipped by terminal height and the banner
    # takes up to INTERVENTION_H more of it. That is the deliberate
    # trade canon asks for ("a halt muscles a bold-yellow row ahead of
    # everything optional") -- pinned by
    # `tests/test_cockpit_stopbanner_wiring.py::
    # test_the_banner_costs_the_center_viewport_rows_only_below_37_lines`
    # so a future change that widens the cost fails loudly.
    #
    # `max(0, column_h - 1)` keeps the column band at >= 1 row: the
    # banner shrinks (3 -> 2 -> 1) and finally drops entirely rather than
    # consuming the whole body. At today's MIN_LINES=20 floor `column_h`
    # is >= 14 before this carve, so the full 3-row banner always fits
    # and the shrink/drop path is a latent guard for a future floor
    # change -- same shape as `LOGS_MIN_H`'s own clamp above.
    banner_h = 0
    if needs_attention:
        banner_h = min(INTERVENTION_H, max(0, column_h - 1))
        column_h -= banner_h

    if column_h > 1:
        control_strip_h = 1
        column_h -= 1
    else:
        control_strip_h = 0

    logs = {"y": rest_y + column_h, "x": ox, "w": i_cols, "h": logs_h_actual}
    banner_y = rest_y + column_h + logs_h_actual
    intervention = (
        {"y": banner_y, "x": ox, "w": i_cols, "h": banner_h} if banner_h > 0 else None
    )
    control_strip = (
        {"y": banner_y + banner_h, "x": ox, "w": i_cols, "h": control_strip_h}
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

    # The right gutter still mirrors the center viewport's height only
    # (``center_h``, unchanged by this WO). The LEFT gutter is different as
    # of WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS: FORMATIONS is a genuinely
    # TALL panel that claims the whole ``column_h`` slot below GOALS -- the
    # spare height below the viewport that used to sit "deliberately
    # unclaimed" (pre-this-WO comment, now claimed on purpose) -- rather
    # than stopping at ``center_h`` like the sibling FOCUS box it replaces
    # did. This is what "tall FORMATIONS panel down toward LOGS" (DECISION
    # `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 5) means concretely:
    # on a generously tall terminal FORMATIONS now runs well past the
    # viewport's own bottom edge, down to LOGS.
    #
    # GOALS claims up to ``GOALS_BOX_MIN_H`` off the top first (its own
    # nested-FOCUS box included, see ``GOALS_BOX_MIN_H``'s own comment);
    # FORMATIONS gets whatever remains below it. GOALS is present at
    # 1x1-or-taller whenever the slot exists at all (``pri_w > 0``) — never
    # dropped in favor of FORMATIONS; FORMATIONS is what shrinks, then drops
    # (``None``) once GOALS alone has consumed the whole slot. Same width
    # for both (stacked, not side-by-side), so every existing PRIORITIES_W /
    # PRIORITIES_MIN_W tier width stays unchanged. ``left_gutter`` keeps its
    # pre-this-WO key -- it was FOCUS's key, now it's FORMATIONS' -- the same
    # "reuse the existing key for whichever occupant sits below GOALS" shape
    # ``right_gutter`` already uses for HUD.
    goals = None
    left_gutter = None
    if pri_w > 0:
        goals_h = min(GOALS_BOX_MIN_H, column_h)
        goals = {"y": rest_y, "x": ox, "w": pri_w, "h": goals_h}
        formations_h = column_h - goals_h
        if formations_h > 0:
            left_gutter = {"y": rest_y + goals_h, "x": ox, "w": pri_w, "h": formations_h}

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
    # The Phase-5 intervention/STOP strip this block used to forecast has
    # LANDED (WO-P5-064) -- it is the ``intervention`` region carved
    # above, and this stacked-gutter shape needed no change to accommodate
    # it. See that carve's own comment for where it actually claims its
    # rows (out of ``column_h``, ahead of the control strip, never out of
    # LOGS) and how that differs from what the forecast here predicted.
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

    # WO-PLAY-CHAIN-BUBBLE-VIZ: optional five-row strip directly under the
    # bordered 80×25 viewport. Appears only when column_h already has five
    # wholly spare rows after preserving VIEWPORT_H — never shrink center.
    chain = None
    spare_under_center = column_h - center_h
    if (
        border
        and center_h == VIEWPORT_H
        and spare_under_center >= CHAIN_VIZ_H
    ):
        chain = {
            "y": rest_y + center_h,
            "x": center_x,
            "w": center_w,
            "h": CHAIN_VIZ_H,
        }

    return {
        "mode": mode,
        "message": None,
        "outer": outer,
        "strip": strip,
        "goals": goals,
        "left_gutter": left_gutter,
        "center": center,
        "chain": chain,
        "right_gutter": right_gutter,
        "decisions": decisions,
        "logs": logs,
        "intervention": intervention,
        "control_strip": control_strip,
    }


def nested_focus_region(goals: dict | None) -> dict | None:
    """FOCUS's own nested sub-box within a GOALS outer region
    (WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS, DECISION
    ``RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`` point 5: "GOALS outer box
    with FOCUS nested inside" -- box-in-box, not two stacked siblings each
    paying for their own outer border).

    Deliberately NOT one of ``frame_layout``'s returned top-level regions:
    it overlaps ``goals`` by construction (it lives INSIDE it), which would
    break every sibling-region "never overlap" invariant the rest of this
    module's regions hold. Callers that need it (``screens.py``'s draw pass,
    this module's own pty test suites) compute it from the already-resolved
    ``goals`` rect via this pure helper instead.

    Reserves GOALS' own top border row plus ``GOALS_CONTENT_H`` digest rows
    before FOCUS's own box begins; the remaining rows down to GOALS' own
    bottom border become FOCUS's slot, at the same width as GOALS (nested,
    not side-by-side). Returns ``None`` when ``goals`` itself is
    ``None``/absent, or when the remaining slot has no room left for even a
    minimal 2-row box (a top+bottom border with zero content rows) --
    degrading to "no nested FOCUS" rather than a negative-height rect, the
    same "drops to None under height pressure" convention every other region
    in this module already follows. Unreachable at every size this module's
    own ``GOALS_BOX_MIN_H``/``FOCUS_NESTED_BOX_H`` constants are sized for
    (they are the very numbers that guarantee this fits whenever ``goals``
    itself reached its own full floor); it only fires when ``goals`` was
    ITSELF clamped short of that floor (an extremely height-starved
    terminal), i.e. the same "goals claims height first" degrade path
    ``frame_layout``'s own pri_w block documents.
    """
    if goals is None:
        return None
    focus_y = goals["y"] + 1 + GOALS_CONTENT_H
    focus_h = goals["y"] + goals["h"] - 1 - focus_y
    if focus_h < 2:
        return None
    return {"y": focus_y, "x": goals["x"], "w": goals["w"], "h": focus_h}
