---
type: System
title: The Trainer Cockpit — Panels, HUD & Live-View Layout
description: The framed oversight dashboard the operator watches — its panel inventory and regions, the always-on tracked-model HUD, the responsive fold, and the liveness signals that show at a glance what the app is doing.
tags: [surfaces, cockpit, spectate, hud, layout, panels, focus, goals, decisions, coverage-meter, liveness, responsive-fold, hud-seed, prescriptive]
timestamp: 2026-07-24T22:57:00Z
---

The Trainer Cockpit is the single framed screen an operator keeps in front of them while the app
pilots: a native TradeWars viewport in the center, the app's read of the world wrapped around it,
and — always — a legible answer to the two questions a human watching a machine play actually asks,
"what is true right now?" and "is it still alive?" It is the **oversight dashboard**, not the
control contract: it *renders* what the app is doing and every live number it has, but the keys that
operate the app — the mode toggle, the A/R/T teach moves, the run/record/panic cluster, the STOP
banner — are specified by [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md),
which this frame merely gives a home. The cockpit's own job is layout and truth: a fixed panel
grid, a HUD that persists the tracked model across screens that don't restate it, a meter that shows
how much of the live driving is the app versus the human, and enough motion that a settled screen
never reads as a frozen one. It is a **read-only** surface — a spectator holds no control-lock (see
[spectate-and-attach](/surfaces/spectate-and-attach.md)); nothing on this dashboard sends a
keystroke. This concept is prescriptive: it specifies the reborn cockpit and records where the built
`spectate_app.py` / `spectate_layout.py` code diverges.

# Schema

## The frame and its regions

The cockpit is one bordered outer frame around three stacked bands. Top is a **character/profile
strip** (which player, which server-world). The middle is a **three-column body**. The bottom is a
full-width **`[LOGS]`** transcript tail. Below everything sits the control strip — rendered here,
owned elsewhere (see the N5 boundary).

```
┌ Character / Profile — host · game · character ──────────────────────────────┐
│ [GOALS]        │                                    │ [HUD]                 │
│  ✓ · ?  status │        [ GAME UI ]                  │  credits/sector/turns │
│ ─────────────  │   native 80×25 zero-inset viewport  │  cargo · ✦ Ns ago     │
│ [FOCUS]        │                                    │ ───────────────────── │
│  ranked        │                                    │ [DECISIONS]           │
│  suggestions   │  [CHAIN]  ○→○→○→○  bubble row       │  trace: kind · gates  │
│ ─────────────  │                                    │  live metrics array   │
│ [FORMATIONS]   │                                    │                       │
├────────────────┴────────────────────────────────────┴───────────────────────┤
│ [LOGS]  session transcript tail                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  «control strip — mode badge · → TX · A/R/T · run/record/panic»  (owned by    │
│   mode-line-and-teach-controls — see N5 boundary)                             │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Left gutter** — three stacked panels, top to bottom:

- **`[GOALS]`** — Layer-1 status. Each strategic prerequisite on its own line with a readable label
  and a status glyph: **`✓`** known / met, **`·`** in progress / partial, **`?`** unknown. The
  authored line set is Turns, Credits, StarDock, Map, Formations, Chain, Ship prices, Hold price,
  Fighters (`compose_primary_goals_lines`, fed by a `GoalsSnapshot`). This layer is **read-only
  context — it does not pick the next action**; it says only how much of the world is known yet.
- **`[FOCUS]` / `[PRIORITIES]`** — Layer-2, the ranked list. **FOCUS is a list of *suggestions*,
  never the app's chosen action.** It shows the engine-ranked effort candidates for the current tick
  (Trade chain / Upgrade / Explore), highest expected-value first, with a gate glyph `⊘` and reason
  on any candidate that is skipped. It is the reborn reframe of the old EV weigh-list: a recommended
  ordering the operator reads, not a commitment the app has made. The ranking source is the priority
  engine — see [priority-engine](/engine/priority-engine.md) — and FOCUS only *displays* its output.
- **`[FORMATIONS]`** — discovered galaxy topologies by name with a short blurb
  (`compose_formations_panel`); the route-hazard-relevant subset (one-way, warp-sink) is what feeds
  the guards elsewhere.

**Center column** — the app's window onto the game:

- **`[GAME UI]`** — the **native 80×25 viewport, zero-inset**: the real TradeWars screen, bordered
  to 82×27 (`VIEWPORT_W/H = GAME_W+2, GAME_H+2`) but never padded inward — the content area is always
  the untouched native grid so what the operator sees is exactly what the app sees.
- **`[CHAIN]`** — a bubble row visualizing the current best trade-loop cycle (`compose_chain_bubbles`
  over the same chain object the engine ranks), plus a You-Are-Here menu-map marker when the app is
  navigating menus rather than trading.

**Right gutter** — the always-on live read, top to bottom:

- **`[HUD]`** — the tracked-model vitals (below).
- **`[DECISIONS]`** — the trace detail behind the current tick: the chosen action kind, its
  rationale, and any gate reasons (`format_autopilot_trace_lines`), plus a **live-metrics array** of
  world counts (stations / planets / fighters / mines / problem-sectors) aggregated from the
  world-model (`aggregate_world_metrics`, `_LIVE_METRIC_SPECS`). GOALS says *what is known*, FOCUS
  says *what is worth doing*, DECISIONS says *what the app is actually reasoning right now*.

**Bottom band** — **`[LOGS]`**, the running session transcript tail, full width.

Data behind HUD and DECISIONS is the semantic screen read plus the persisted world database — see
[screen-understanding](/engine/screen-understanding.md) and [world-model](/engine/world-model.md).
The two-layer GOALS-vs-FOCUS split (informational status over action ranking) is the cockpit
expression of the north-star's two-layer information architecture — see
[north-star](/architecture/north-star.md).

## The always-on HUD and its freshness

The HUD's defining property: it shows the **tracked model**, not the current screen. TradeWars
scatters credits, sector, turns and cargo across screens and omits them entirely on many (explore
and combat screens routinely state neither credits nor turns), so a naive "parse the current screen"
HUD would blink to `-` constantly. Instead each cell **persists its last-known value** and stamps it
with an age: `✦ Ns ago` (`format_freshness`, mark `✦`), dimming once a cell goes stale past
`FRESHNESS_STALE_S` (20s). The operator always sees a number and always sees how old it is.

**Data-source rule (N4/N8).** A HUD cell's live value comes from the **corrected current screen
text** through the strict snapshot paths (credits via `credits_snapshot()`, turns via
`turns_snapshot()` — never a loose screen scrape). The **trace ledger is history only** — it records
what happened for retro and learning and is never read back as a live HUD value. Live truth flows
screen → tracked model → HUD; the ledger is a one-way sink (see [trace-ledger](/engine/trace-ledger.md)).

**Cold-join HUD seed (`hud_seed.py`).** This is the mechanism *behind* "persists across
credits-less screens." When a spectator attaches (or `ensure` finishes login) onto a screen that
states neither credits nor turns, every HUD cell would sit at its sticky `-` forever because nothing
on screen ever restates the value. `seed_hud_after_join()` breaks that: at a safe command prompt it
sends the single **`I` ship-info probe** exactly once when either credits or turns is still unknown,
observes the resulting ship-info screen, and fills the sticky cells. A `force=True` re-probe is
age-gated for long explore runs where the values have gone stale. The probe is **deliberately
deferred on a fighter `Option?` dialogue** — there `I` means *Info*, not ship-info, and probing
would scroll the `Your fighters: N vs. theirs: M` line off pyte's 25-line viewport before the app
could Attack/Retreat. The seed never raises: a failed probe must not break the join. This is the one
place the dashboard causes a send, and it is a safe read-only introspection, not a play move.

## Liveness and TX transparency — killing "is it frozen?"

A machine on a settled screen and a machine that has hung look identical unless the dashboard proves
otherwise, so the cockpit carries continuous motion signals (N6/N7/N8):

- **Sparklines and gauges** — a recent-credits sparkline (`render_sparkline`, `CREDIT_SPARK_WIDTH`
  20 samples), a turns-left fuel gauge (`render_bar_meter`, `TURNS_GAUGE_WIDTH` 10), port commodity
  %-meters (`PORT_BAR_WIDTH` 10) — history the eye can read at a glance.
- **Delta-flash and count-up** — a credits change tweens (`CREDIT_TWEEN_DURATION_S` 0.3) and flashes
  a delta chip (`CREDIT_FLASH_DURATION_S` 1.5); the newest LOGS/ticker row flashes on arrival
  (`TICKER_FLASH_DURATION_S` 1.0); a classification change pulses (`CLASSIFICATION_PULSE_DURATION_S`
  1.0). All are `is_recent`-gated so they decay, never stick.
- **Waiting spinner** — while the session is connecting or between events the center shows an
  explicit waiting screen (`waiting_session_screen`) rather than a blank grid.
- **The `→ TX` sent-keystroke channel (N6/N7/N8)** — a live readout of what the app just sent:
  `→ 158` when input went out, `→ -` when idle (`format_tx_readout`). It is paired with the ticker
  outcome so the operator sees *the app sent this* alongside *this is what came back* — the send and
  its result on screen together. The value is **already redacted upstream** (a `--secret` send
  arrives pre-masked from `Session.send()`), so a password never reaches this channel — see
  [secrets-and-credentials](/doctrine/secrets-and-credentials.md).

## The coverage / auto-% meter

A small footer gauge (`compose_autonomy_footer_box`, at the bottom of the left gutter so it never
clips the HUD's PORT meters) answers "how much of the live driving is the app doing versus me?" The
reborn meter is an **App-vs-Human live share**: of the keystrokes actually sent to the game this
session, what fraction were the app's deterministic play versus the human's own hands on the
keyboard. **"AI" is not a slice of this live meter** — the AI teacher never sends a live keystroke,
so its live share is identically zero. AI provenance is a **separate teaching axis** (how many armed
rules were authored or approved with the teacher's help), reported elsewhere, never mixed into
live-drive share. The exact math — what counts, the window, how the teaching axis is derived — lives
in [coverage-metrics](/engine/coverage-metrics.md); the cockpit only renders the number.

## Responsive fold

The body is width-tiered and **never scrolls horizontally** — content that cannot fit is folded, not
pushed off-edge (`frame_layout`). The load-bearing breakpoints (from `VIEWPORT_W` 82 + the gutters):

| Width (cols) | What renders |
|---|---|
| ≥ `FULL_GUTTER_MIN_COLS` (154) | Full left gutter (GOALS/FOCUS/FORMATIONS) + viewport + right HUD gutter |
| ≥ `LEFT_GUTTER_MIN_COLS` (138) | Narrow left gutter (`PRIORITIES_MIN_W` 20) still present + viewport + HUD |
| ≥ `RIGHT_GUTTER_MIN_COLS` (118) | Viewport + right HUD only; **GOALS + FOCUS fold into the idle DECISIONS pane** |
| ≥ `MINIMAL_HEADER_MIN_COLS` (82) | Bordered viewport alone (`== VIEWPORT_W`, the floor at which a framed 80×25 fits) |

Below `LEFT_GUTTER_MIN_COLS` (138) the left-gutter GOALS and FOCUS panels **collapse into the idle
DECISIONS pane** rather than disappearing — the operator keeps the status and the ranked suggestions,
just relocated. The viewport is the last thing to survive; the body never sacrifices horizontal
legibility for panel count.

## N5 boundary — rendered here, owned elsewhere

The bottom **control strip** — the mode badge, the `→ TX` readout position, the A/R/T teach keys, the
run / record / panic control cluster, and the pop-up **Trade-Loop-Chains library** — is *drawn
inside this frame* but is **not authored by this concept**. Its interaction contract (what the keys
do, the App/Human mode dual with no third "AI drives" slot, the confirm-gate before any
rule-arming / run-launch, and the typed reason-code STOP banner) belongs to
[mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md). The cockpit gives these
controls a home and a place on the grid; it does not define their behavior. Treat that concept as
authoritative for everything on the control strip.

## Exit flow — stop the daemon too?

*— per [ADR-001](/ADR/001-one-tree-embedded-session.md) (Accepted 2026-07-24)*

The aiclient app the operator is watching in this frame is not the daemon: `twd` is continuity, the
app is disposable (see [Session Engine](/architecture/session-engine.md)'s Rolling-Pilot Operating
Model). That means quitting the cockpit is not automatically the same thing as ending the game
session — the daemon can keep the one telnet connection alive for a later reattach, or it can be
stopped along with the client. The cockpit does not decide this silently either way: on the
operator's exit from the app, a **confirm popup** asks — **"Stop the daemon too? (Yes / No)"** —
before the app itself closes. The popup **defaults to No** (leave the daemon running; the session
stays reattachable) — the lower-risk, non-destructive outcome if the operator just hits Enter;
stopping the daemon requires actively moving to and confirming **Yes**. `tw stop` is the deliberate,
explicit verb for a full stop outside this flow. The popup is a plain confirm-gate, the same weight
as the launch confirm-gate mode-line-and-teach-controls specifies for arming a run: one explicit
choice always asked, never a silently *auto-applied* action — a stated default on the gate is not
the same as skipping the gate.

This mirrors [Entry & Profile Selection](/surfaces/entry-and-profile-selection.md)'s hand-off at the
other end of the session: that surface hands a chosen profile *into* the cockpit at launch; this is
the cockpit's own hand-back *out* when the operator is done — the app-lifecycle bookend to the
launcher's hand-off. The exact keybinding and popup styling belong to the control strip's
interaction contract, owned by
[mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md) per the N5 boundary above;
this section states only that the choice exists and is asked, never assumed.

# Visual design & polish

Everything above specifies *what* the cockpit shows and *where*. This section specifies how it
**looks** — the colors, box-drawing, spacing, motion, and states that make a dense terminal grid
read as one calm, honest instrument. Every concrete glyph, color, and threshold below is grounded
to a code module (or marked `[ASPIRATIONAL]` where it is intent-not-yet-built). The vocabulary here
— the 7-tone color table, the glyph set, the two-weight border hierarchy, the liveness-cue catalog —
is **shared verbatim across all four surface docs** (cockpit, mode-line, spectate/attach, entry);
it is the same code paths (`spectate_layout.py` / `terminal.py`) rendering every surface. The
canonical single-source home for the shared vocabulary is
[visual-language](/surfaces/visual-language.md) *(forward-reference — a staged concept pending
operator go-ahead; until it lands, the tables below are the working reference and this doc is the
most-referenced surface that carries them)*. What stays local to this doc is the cockpit's own
**application** of that vocabulary: the HUD cell order, gutter widths, the fold ladder, the
intervention strip's height claim.

## Color semantics — the one 7-tone table

A single semantic palette (`_SEMANTIC_COLORS`, `spectate_app.py`) drives the whole dashboard, so a
color always means the same thing on every panel. pyte color-names map to curses basic-8 via
`_PYTE_TO_CURSES_COLOR` (`spectate_app.py`); note pyte names ANSI-yellow `"brown"` but it renders
**yellow** everywhere.

| tone | fg / attr | Meaning | Representative cockpit uses |
|---|---|---|---|
| `ok` | green / **bold** | good · profit · healthy · full gauge | turns fuel-gauge ≥50%, PROFIT positive, port "buying" row, AUTO-LOOP badge |
| `warn` | yellow / **bold** | warning · stale · attention-needed | turns-gauge 20–50%, the intervention strip, MANUAL badge |
| `danger` | red / **bold** | hostile · disconnected · critical | turns-gauge <20%, disconnected status, credit-loss flash |
| `info` | cyan / non-bold | menus · neutral chrome · selling | **all box chrome (borders/titles/dividers)**, port "selling" row, the AI-teach overlay badge |
| `gain` | green / **bold** | positive credit-delta flash | CREDITS cell flash-up |
| `loss` | red / **bold** | negative credit-delta flash | CREDITS cell flash-down |
| `muted` | default / non-bold | parked · "nothing to see here" | SPECTATE badge (genuinely uncolored — there is no grey in basic-8) |

Two shared classifiers emit only `ok`/`warn`/`danger` and are the source of every gauge/status tint:

- **`status_semantic(connected, last_rx_age_s)`** (`spectate_layout.py`) — `danger` if disconnected;
  `warn` if `last_rx_age_s ≥ 5.0` (`_STALE_RX_THRESHOLD_S`); else `ok`.
- **`gauge_semantic(fraction)`** (`spectate_layout.py`) — `ok` ≥0.5, `warn` ≥0.2, else `danger`.
  This is what colors the turns fuel-gauge green→amber→red as turns drain.

Three load-bearing color rules:

- **Cyan is chrome, never data.** Every box border, title, and divider is cyan (the outer frame is
  cyan **bold**); the chain-bubble viz is cyan + `A_DIM`. Data never wears the chrome color, so the
  eye separates instrument-frame from instrument-reading without thinking about it.
- **Reverse-video (`A_REVERSE`) is the *one* selection/active/badge signal** across the entire UI —
  the mode badge chip, the selected Loops/Chains row, the live-play `y/N` confirm (danger + reverse),
  the classification-change header pulse, the connect/disconnect status flash. There is no second
  "this is selected" convention to learn.
- **The viewport border is a STATE surface.** It flips cyan → **red non-bold** the moment the daemon
  reports `not connected` (`spectate_app.py`) — an unmissable "link down" cue drawn on the frame
  itself, never touching game content.

**Per-cell game color is distinct from the dashboard tint set.** Inside `[GAME UI]`, `terminal.color_map()`
(`terminal.py`) RLE-encodes pyte's true SGR fg/bg/bold per row, and `_ColorPairs` (`spectate_app.py`)
lazily allocates a curses pair per distinct (fg,bg), degrading to plain bold/normal when the pair
table is exhausted. The viewport therefore renders in the **server's own CP437 palette**, not the
7-tone semantic set — what the operator sees is exactly what the app sees. `[ASPIRATIONAL/HYPOTHESIS]`
the stock-TradeWars convention that "red = hostiles, cyan = menu chrome" in that native palette is
**unverified** and must stay hypothesis-marked, never promoted to fact.

**Cut, deliberately:** no light theme (dark + high-contrast only, `TUI-POLISH-PLAN.md`). The whole
palette is monochrome-plus — one table, seven meanings, one selection attribute.

## Box-drawing, borders & titles — a two-weight hierarchy

The frame uses a deliberate **two-weight** border system (`terminal.py`, `GLYPHS_UNICODE` /
`GLYPHS_ASCII`, switched by a single `unicode_ok` flag so every glyph has an ASCII twin):

| element | Unicode | ASCII |
|---|---|---|
| **viewport** corners/edges | `╔ ╗ ╚ ╝` `═` `║` (double-line) | `+ = \|` |
| **HUD / all chrome** corners/edges | `╭ ╮ ╰ ╯` `─` `│` (thin rounded) | `+ - \|` |

- **Double-line = the live game; thin-rounded = every instrument.** The heavier border is a
  focus signal — a deliberate BBS/DOS-door echo (`TUI-POLISH-PLAN.md` Phase 1). The eye lands on the
  CP437 world first; the rounded HUD panels frame it without competing.
- **Outer frame:** one double-line box around the *whole* client (`_draw_outer_frame`, cyan **bold**)
  — the unifier that makes the three bands read as a single cockpit rather than four stacked widgets.
- **Viewport zero-inset is an invariant, not a style choice.** The `[GAME UI]` box is titled
  `" GAME "` with the border on row/col 0 and content at (1,1), **zero inner padding**
  (`_content_inset`, `spectate_app.py`). Any inward pad would shear the game's own CP437 box-art —
  this is why `VIEWPORT_W/H = GAME_W+2, GAME_H+2` (82×27) and never a padded inset.
- **Titled thin boxes** carry their title at `addnstr(0, 2, " TITLE ")` in cyan: `HUD`, `LOG`,
  `DECISIONS`, `PRIORITIES`, `FORMATIONS`, `MENU MAP`, `TRADE LOOP CHAINS`.
- **Chain bubbles** are rounded `╭─╮ │ ╰─╯` joined by a heavy `═════` connector (`_CHAIN_CONNECTOR`)
  — the one place a chrome element borrows the viewport's heavier weight, marking the trade loop as
  the "live" instrument. The autonomy footer is a nested rounded box.

## Spacing, alignment & hierarchy — what draws the eye first

The composition has a fixed reading order, enforced by geometry:

- **Gutter widths are fixed and symmetric:** `HUD_GUTTER_W = 36` on the right, `PRIORITIES_W = 36`
  on the left (`spectate_layout.py`), sized so the CREDITS value plus its freshness stamp (plus the
  sparkline) fit without wrapping. The center viewport is whatever remains
  (`middle = i_cols − PRIORITIES_W − HUD_GUTTER_W`), keeping the game grid centered between two
  equal instrument rails.
- **CREDITS is the primary metric and it is cell #1.** The HUD renders in a fixed operator order —
  **`CREDITS · SECTOR · TURNS · CARGO · PROFIT`** (`compose_hud_cells`, `_HUD_FIELD_SPECS`) — top of
  the right gutter, first thing read. Labels are `A_BOLD`; the value carries the full emphasis stack:
  semantic tone + a floating delta chip + the recent-credits sparkline. SECTOR/TURNS/CARGO/PROFIT
  follow in a uniform 2-row cell stride so the column stays scannable.
- **The eye goes: game → HUD → left-gutter status.** Border weight pulls to the viewport, the bold
  bright CREDITS cell anchors the right rail, and the left gutter (GOALS/FOCUS/FORMATIONS) reads as
  supporting context. Nothing in the calm state competes for attention with color noise.

## Panel states — active, stale, empty, alert

- **Stale / blurred.** Any persisted HUD cell dims to `A_DIM` once its value ages past
  `FRESHNESS_STALE_S` (20s) untouched — the number stays (never blanks to `-`) but visibly recedes,
  so "old" and "current" are distinguishable at a glance.
- **Empty panels state their emptiness honestly** rather than vanishing: FORMATIONS shows
  `"(none yet — map warps)"`, DECISIONS shows `["—", "Exploring…"]`, MENU MAP shows `here off-map`,
  PRIORITIES shows `"—"`. An empty panel is a known-nothing, not a bug.
- **Attention → the intervention strip claims height first.** When the app `needs_attention`, a
  single warn-colored (**yellow bold**) row `! {label}; {label}` is pinned directly above the status
  bar, its labels drawn from typed reason-codes (`intervention_reason_label`; an empty code renders
  `"?"`). Critically, `frame_layout` allocates this row's height **before** control strip and ticker
  (`needs_attention and leftover >= 1`) — a halt always surfaces even on a height-starved terminal.
  This is the concrete mechanism behind "the eye is pulled to the escalation." *(The strip's full
  interaction contract and STOP-banner styling are owned by
  [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md) — see the N5 boundary.)*

## Liveness & motion — the "is it frozen?" killers

Animation is decoupled from content so motion never costs a redraw storm: chrome animates at
`ANIM_FPS = 13`; the viewport redraws only on a real settle-edge event; a disconnected session drops
to a slow `IDLE_ANIM_INTERVAL_S` idle. The always-running cues:

| cue | glyph / const | behavior |
|---|---|---|
| waiting spinner | braille ramp `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` (ASCII `\|/-`) | advances while connecting/between events; frozen at `[0]` when calm |
| heartbeat | `●`/`○` (ASCII `*`/`.`), `HEARTBEAT_PERIOD_S = 0.8` | always breathing — slower than the spinner, so "alive" reads even on a settled screen |
| credit sparkline | `▁▂▃▄▅▆▇█` (ASCII `.-=#`), `CREDIT_SPARK_WIDTH = 20` | scaled to its own min/max; flat series → middle glyph |
| turns fuel-gauge | `[████░░░░░░]`, `TURNS_GAUGE_WIDTH = 10` | green→amber→red via `gauge_semantic` as turns drain |
| delta chip + tween | `{delta:+,} ▲/▼`, `CREDIT_FLASH_DURATION_S = 1.5`, tween `0.3s` | slot-machine count-up on a credits change, then fades |
| ticker flash | newest LOG row bold, `TICKER_FLASH_DURATION_S = 1.0` | flags a just-arrived transcript line |
| classification pulse | header reverse-video, `1.0s` | pulses when the screen classification changes |
| freshness stamp | `✦ Ns ago` / `✦ now` (ASCII mark `*`), `format_freshness` | on every persisted value; dims past 20s |
| `→ TX` channel | `→ 158` sent / `→ -` idle, `format_tx_readout` | the live sent-keystroke readout, paired with the ticker outcome |

All flashes are `is_recent`-gated: they decay and never stick, so the steady state settles back to
quiet. (The `→ TX` value is already redacted upstream — a `--secret` send arrives pre-masked from
`Session.send()`, so a password never reaches this channel; see the HUD/TX sections above.)

## Empty / loading / cold-join / error / off-map states — concretely

- **Cold-join / loading.** A connecting or between-events session shows the explicit
  `waiting_session_screen` (`WAITING_SESSION_LINES`) in the center — a calm placeholder, never a
  blank grid and never a stale login prompt. The HUD may cold-start all-`-`; that is where the
  `hud_seed.py` single-`I` probe fills the sticky cells (see the Cold-join HUD seed section above).
- **Reconnecting.** On a drop, the viewport border reddens and a bounded backoff
  (`0.25 → 3.0s`, ~5 attempts) drives a `Reconnecting…` indicator; exhaustion surfaces a
  `reconnect_exhausted` state rather than silently spinning.
- **Error.** An error renders as `! {error_text}` on the status line's left, and the **host is always
  still shown** — the operator never loses the "which world am I on" anchor even in an error state.
- **Off-map.** The MENU MAP is honest about the unknown: `here off-map` when the current sector isn't
  placed, versus `here ★ {label}` when it is (`menu_map_view.py`) — never a guessed position.
- **Too-small.** Below the floor the frame refuses with `Terminal too small (C×L) — need at least
  60×20` rather than rendering a broken layout.

## Responsive fold — aesthetics of graceful collapse

The fold ladder (specified in full in the Responsive-fold section above, `frame_layout`) is a
*visual-dignity* contract as much as a layout one: **the body never scrolls horizontally.** Content
that cannot fit is folded, not pushed off-edge — the viewport stays ≤80 wide, LOG truncates to its
line-tail, and chain bubbles truncate left→right with a `… Nh` marker. Panels shed by column budget
in a fixed priority (full gutters → narrow left gutter → right HUD only, with GOALS+FOCUS folding
*into* the idle DECISIONS pane → bordered viewport alone), and height degrades
header→control→ticker→viewport-border in that order. The viewport is always the last thing to
survive. Degradation is designed to lose *chrome and redundancy*, never *information*.

## Glyph / status-marker vocabulary

Two parallel glyph tables switch on one `unicode_ok` flag (`glyph_set()`), so a non-UTF-8 terminal
loses fidelity but never meaning. The marker set the cockpit uses:

- **GOALS / FOCUS status:** `✓` met / known · `·` in progress / partial · `?` unknown · `⊘` blocked
  (an unmet prerequisite; also a gated FOCUS/autopilot candidate) — `compose_primary_goals_lines`.
- **Autopilot-trace (DECISIONS):** `★` chosen action · `·` other candidate · `⊘` gated.
- **Highlight / selection / location:** `★` centerpiece — you-are-here (`here ★{cur}`), the MENU MAP
  marker, the longest Loops chain · `▸` the selected/armed row marker · `○ ○` the empty-chain
  placeholder (`○ ○  no trade loop yet`).
- **Flow / freshness / separators:** `✦` freshness mark (NON-NEGOTIABLE per `TUI-POLISH-PLAN.md`) ·
  `—` em-dash for an unknown/empty value · `→` sent-key / step arrow · `⇒` the LOG "landing differs"
  suffix · `·` the header separator.
- **Motion glyphs:** spinner `⠋…⠏` · heartbeat `●`/`○` · sparkline `▁…█` · fuel/bar `█`/`░` ·
  delta chip `▲`/`▼` (ASCII twins `\|/-` · `*`/`.` · `.-=#` · `#`/`.` · `^`/`v`).
- **Mode badges** (`_MODE_BADGES`, reverse-video tone-colored chips): `AUTO-LOOP` (ok/green) ·
  `MANUAL — YOU HAVE CONTROL` (warn/yellow) · `SPECTATE` (muted/plain) · the AI-teach badge
  (info/cyan) is a **teach-overlay indicator** shown while an Analyze pass is open — **not** a live
  drive-mode. *(The build's `_MODE_BADGES` still carries an `ai_pilot: "AI-PILOT"` entry — the
  recorded divergence from the App/Human dual; see Code divergence.)*

## Feel — the builder's north star

**Dense-but-readable, terminal-native, calm-until-it-needs-you.** The cockpit is an old-fashioned
trainer's console — you watch a trainee learn, then deploy what it learned (`TUI-POLISH-PLAN.md`).
Concretely, a builder should aim for:

- **One composition.** A single double-line outer frame, cyan chrome accent, two-weight border
  hierarchy giving the CP437 game screen visual primacy — game first, instruments frame it.
- **Honest liveness everywhere.** Nothing reads as silently-current: every value carries `✦ Ns ago`
  and dims at 20s; heartbeat and spinner run always; changes announce (chip / tween / ticker-flash /
  pulse) then fade back to quiet.
- **Calm baseline, loud escalation.** Steady state is near-monochrome and still (muted badge, frozen
  spinner, no color noise). A halt muscles a bold-yellow `!` strip ahead of everything optional. Red
  is *reserved* — a disconnection reddens the game frame's own border rather than shouting elsewhere.
- **Never lie, never invent.** Unknown → `?` / `—` / `off-map`; a stale port's meters vanish on
  undock; a gated action wears `⊘`.
- **Degrades with dignity.** Unicode/ASCII twin tables lose zero information; panels fold by column
  budget; the body never scrolls sideways.
- **Hand-built and lean.** Pure stdlib `curses`, zero new packages (`rich`/`textual`/`blessed`
  rejected). The anti-gold-plating is itself part of the taste — cut list: light theme, powerline
  separators, pane intro-stagger, full-grid marquee (`TUI-POLISH-PLAN.md`).

# Implementation status (tip `7af4dbd` · Phase 3 CLOSED · Phase 4 OPEN)

| Band | Tip reality |
|---|---|
| Outer frame · strip · three-column body · fold | **LIVE** (PWO-031…033 · 039) |
| GOALS · FOCUS · DECISIONS · HUD freshness · TX/liveness · tones · LOGS | **LIVE** (PWO-034…041 · tip `6391bb7`) |
| Center `[GAME UI]` content | **LIVE** — blank 80×25 GAME shell (PWO-051 · tip `7af4dbd`); `_GAME_PLACEHOLDER` retired. Live pyte paint is **NOT** yet (PWO-052) |
| Product watch-stream into play shell | **LIVE** subscribe (PWO-050 · `watchfeed.py` · tip `b211be2`); snapshot→paint is **NOT** (PWO-052) |
| Mode line / teach A·R·T / STOP strip | **NOT** Phase 3 — Phase 5+ |
| Coverage meter / chains library / formations | **NOT** on tip play shell (archive / later WOs) |

Citations below that name only `spectate_app.py` / `spectate_layout.py` are **port-source** until the
reborn module is cited; prefer `tw2002_aiclient/cockpit/*` for chrome that has already landed.

# Code divergence

- **Coverage meter counts the wrong axis.** (Archive / future Phase-5+ surface.) `compute_autonomy_ratio()` /
  `format_autonomy_counts()` in archived `spectate_layout.py` compute the live share as
  `trainer / (ai + trainer)` and render `App N / AI N · Hum N` with **AI inside the live
  denominator and Human excluded from it**. The reborn ruling (operator, 2026-07-23) is the
  inverse: the live meter is **App-vs-Human share**, and **AI live share is identically zero**
  (the teacher never sends live) — AI belongs on a separate teaching-provenance axis, not in the
  live meter. DOCS WIN — the meter math is recast in [coverage-metrics](/engine/coverage-metrics.md);
  this cell's `App/(App+AI)` formula and its `AI` live-denominator term are the recorded divergence.
  **Not on tip play shell today** — recorded so the port does not revive it.
- **Mode badge may still carry an AI/auto-loop live position.** Archived `format_mode_badge()` /
  `_MODE_BADGES` render the control-strip mode from `control_lock`'s modes, which historically
  include `ai_pilot` / `auto_loop` alongside `human`. The reborn mode line is an **App/Human dual
  with no third "AI drives" slot** (AI shows only as a teach-overlay indicator). Any surviving
  AI-as-a-mode badge value is a divergence from that dual; the corrected contract is owned by
  [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md). Tip play shell has **no**
  mode badges yet (Phase 5).

# Citations

- **Panel layout, tiers, fold, HUD cells, freshness, liveness, TX, coverage footer** —
  `spectate_layout.py` (`frame_layout`, `compose_primary_goals_lines`, `compose_priorities_lines`,
  `format_autopilot_trace_lines`, `aggregate_world_metrics`, `compose_hud_cells`,
  `format_freshness`, `render_sparkline` / `render_bar_meter`, `format_tx_readout`,
  `compose_autonomy_footer_box`, and the width/motion constants).
- **Curses I/O host for the above pure layout** — `spectate_app.py` (read-only spectator dashboard).
- **Visual design & polish grounding** — `spectate_app.py` (`_SEMANTIC_COLORS`, `_PYTE_TO_CURSES_COLOR`,
  `_ColorPairs`, `_content_inset`, `_draw_outer_frame`, `ANIM_FPS`, `HEARTBEAT_PERIOD_S`),
  `spectate_layout.py` (`status_semantic` / `gauge_semantic`, `_MODE_BADGES`, `_HUD_FIELD_SPECS`,
  `compose_hud_cells`, `HUD_GUTTER_W` / `PRIORITIES_W`, `FRESHNESS_STALE_S`, `format_freshness`,
  `render_sparkline` / `render_bar_meter`, `compose_intervention_strip`, `frame_layout`'s
  `needs_attention` height claim), `terminal.py` (`GLYPHS_UNICODE` / `GLYPHS_ASCII` two-weight border
  set, `color_map()`), `menu_map_view.py` (`here off-map` / `here ★`), and the polish intent in
  `TUI-POLISH-PLAN.md` (BBS/DOS-door border echo, the anti-gold-plating cut list, dark-only theme).
  Shared vocabulary forward-referenced to the staged `visual-language.md` concept (operator-gated).
- **Cold-join HUD seed** — `hud_seed.py` (`seed_hud_after_join`, the single `I` ship-info probe,
  fighter-`Option?` deferral, age-gated `force` re-probe).
- **Reimagined from** — `USERDOCS/aiclient_ui.md` and the TUI sections of
  `USERDOCS/priority_engine.md` (the original main-UI sketch and the GOALS/FOCUS two-layer panel
  model), re-rooted in the reborn human-piloted vision with all "AI drives / AI as a mode" framing
  struck.
- **Architecture map + hard rules** — the project `CLAUDE.md` (`spectate_app.py` /
  `spectate_layout.py` roles, read-only spectator, secrets-never-logged).
