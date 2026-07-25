---
type: Reference
title: Visual Language — The Shared Color, Glyph & Border Vocabulary
description: The single-source dictionary of color semantics, glyphs, box-drawing weights, liveness cues, and fold thresholds every cockpit surface renders with — the surfaces are the sentences, this is the dictionary.
tags: [surfaces, visual-language, color-semantics, glyphs, box-drawing, liveness, responsive-fold, hud, spectate, prescriptive, reference]
timestamp: 2026-07-25T04:02:00Z
---

Four surfaces — [The Trainer Cockpit](/surfaces/trainer-cockpit.md),
[Mode Line & Teach Controls](/surfaces/mode-line-and-teach-controls.md),
[Spectate & Attach](/surfaces/spectate-and-attach.md), and
[Entry & Profile Selection](/surfaces/entry-and-profile-selection.md) — render through the *same*
rendering code paths (`spectate_layout.py` for pure layout, `spectate_app.py` for the curses host,
`terminal.py` for glyphs and CP437/pyte color translation), so a color, a glyph, or a border weight
means the same thing everywhere it appears. This concept is that shared dictionary, extracted once
so the four surface docs never restate it — they instead forward-reference here and specify only
their own *application* of it (which HUD cell gets which tone, which panel gets which border). If a
value below and a surface doc's inline restatement of it ever drift, this concept is the
single-source authority and the surface doc's copy is a stale echo to be corrected.

Every concrete value below is grounded to the module and, where meaningfully stable, the symbol name
that defines it. **Rebirth tip (Phases 0–3 CLOSED · Phase 4 CLOSED through `bba53d4` · PWO-060
`2ca3154`):** cockpit chrome composers, layout, tones, fold, and LOGS live under
`tw2002_aiclient/cockpit/` and `screens.py`; session transport under `tw2002_aiclient/session/`;
product watch subscribe under `tw2002_aiclient/watchfeed.py` (PWO-050); GAME glyph + per-cell color
paint under cockpit viewport (PWO-052 · PWO-053); disconnect border round-trip + color-unavailable
interim (PWO-054); in-cockpit `SPECTATE` chip (PWO-055); Mode attach + Ctrl-] detach (PWO-056 ·
PWO-057); App XOR Human dual chips + vocabulary gate (PWO-060 — App chip **composer-LIVE**,
**wire-UNREACHABLE** until 061 App-hold). Citations still name many archive
(`archive/pre-rebirth-2026-07-23/code/twclient/`) symbols where Phase 5+ teach / STOP / arm ports
have not landed — those remain the port-source until their WOs ship. Anything not yet built, or
built differently from the reborn contract, is marked `[ASPIRATIONAL]`; any unverified claim about
the game's own native palette is marked `[HYPOTHESIS]` and must never be promoted to fact without
live introspection.

**Implementation honesty — GAME viewport:** the play-shell center paints live settle-snapshot /
pyte **glyphs and per-cell fg/bg/bold color** into the 80×25 GAME (**LIVE** · PWO-052 · PWO-053).
Border STATE flip (danger non-bold / color-unavailable `A_UNDERLINE`) is **LIVE** and reconnect-proven
(P3-040 · PWO-054 · tip `6c7d834`). In-cockpit spectate indicator is **LIVE** (muted `SPECTATE` ·
PWO-055); attach/detach loop is **LIVE** (historically bare `M` · Ctrl-] · chip SPECTATE↔MANUAL · tip `bba53d4`; Mode chord = **Ctrl-A** per ADR-002);
App/Human dual chips are **LIVE** (PWO-060 · tip `2ca3154`); ops `tw spectate` is **RETIRED / WONTBUILD** (Max `@ 13:13:55Z` — folded into cockpit Spectate).
Do not read chrome-tones prose as recoloring game cells with the 7-tone semantic table.

# Schema

## Color semantics — the one 7-tone table

A single semantic palette, `_SEMANTIC_COLORS` (`spectate_app.py`), drives every dashboard surface —
one table, seven meanings, so a color never has to be re-learned per panel. pyte color-names map to
curses basic-8 via `_PYTE_TO_CURSES_COLOR` (`spectate_app.py`); pyte names ANSI-yellow `"brown"` but
it renders **yellow** everywhere — a naming quirk of the library, not a design choice.

| tone | fg / attr | Meaning | Representative uses |
|---|---|---|---|
| `ok` | green / **bold** | good · profit · healthy · full gauge | turns fuel-gauge ≥50%, PROFIT positive, port "buying" row, the App mode badge |
| `warn` | yellow / **bold** | warning · stale · attention-needed | turns-gauge 20–50%, the intervention strip, the Human mode badge |
| `danger` | red / **bold** | hostile · disconnected · critical | turns-gauge <20%, disconnected status, credit-loss flash, the live-play `y/N` confirm |
| `info` | cyan / non-bold | menus · neutral chrome · selling | **all box chrome (borders/titles/dividers)**, port "selling" row, the teach-overlay badge |
| `gain` | green / **bold** | positive credit-delta flash | CREDITS cell flash-up |
| `loss` | red / **bold** | negative credit-delta flash | CREDITS cell flash-down |
| `muted` | default / non-bold | parked · "nothing to see here" | the Spectate badge (genuinely uncolored — there is no grey in curses basic-8) |

Two shared classifiers emit only `ok`/`warn`/`danger` and are the source of every gauge/status tint
across every surface — a surface never invents its own thresholds:

- **`status_semantic(connected, last_rx_age_s)`** (`spectate_layout.py`) — `danger` if disconnected;
  `warn` if `last_rx_age_s ≥ 5.0` (`_STALE_RX_THRESHOLD_S`); else `ok`.
- **`gauge_semantic(fraction)`** (`spectate_layout.py`) — `ok` ≥0.5, `warn` ≥0.2, else `danger`. This
  is what colors the turns fuel-gauge green→amber→red as turns drain.

### Three load-bearing color rules (apply on every surface, no exceptions)

- **Cyan is chrome, never data.** Every box border, title, and divider is cyan (the outer frame is
  cyan **bold**). Data never wears the chrome color, so the eye separates instrument-frame from
  instrument-reading without thinking about it.
- **Reverse-video (`A_REVERSE`) is the *one* selection/active/badge signal** across the entire UI —
  every mode badge chip, the selected Loops/Chains row, the live-play `y/N` confirm (danger +
  reverse, the loudest combination the palette owns), the classification-change header pulse, the
  connect/disconnect status flash, and Attach's active status bar. There is no second "this is
  selected/active" convention anywhere in the bundle.
- **The viewport border is a STATE surface.** On a real `connected: False` it flips cyan chrome →
  **danger fg without the table's bold** (red **non-bold** — a deliberate per-surface override of
  `danger`'s red/bold row in the 7-tone table). Unmissable "link down" on the frame itself, never
  touching game content. Code (PWO-054 · tip `6c7d834`): `screens.py` PlayShellScreen
  `_viewport_border_attr` / draw path — reconnect → cyan proven; silent-border guard when danger
  attr collapses to `A_NORMAL`. **Mono / color-unavailable interim:** the same disconnect flip uses
  `A_UNDERLINE` **non-bold** — `A_REVERSE` stays reserved for selection/active; this underline path
  is an interim DOC-GAP until a stronger mono STATE cue is ratified.

### Mode-badge colors — and the guarded absence

The mode indicator's tone is the single highest-priority piece of color on the mode line, so it is
canonical here, not merely a per-surface style choice:

- **App** (deterministic autopilot holds the keyboard) — **green (`ok`)**. Healthy; the taught app
  is covering the known. **Chip glyph text = `APP`** (Max Batch 2/3; match `APP_LABEL="APP"`).
- **Human** (the live `tw attach` seat holds the keyboard) — **yellow (`warn`)**. Deliberate, not an
  error: with the human flying, autopilot is stood down and the surface is in its
  attention-with-you register — the human is the one thing that must not be ignored.
- **The teach-overlay (AI) indicator** — **cyan (`info`)**, non-bold. `[ASPIRATIONAL]` Shown *only*
  while an Analyze pass is open; it is chrome/neutral by design — an overlay annotation, never a
  live-drive slice — and its non-bold cyan visually separates it from the bold App/Human live-holder
  chips.
- **Spectate** (not a dual member; takes no lock) — **muted / plain**. Deliberately uncolored —
  "nothing to see here," idle/parked.

**There is no "AI drives" badge, by design.** The reborn control model is an **App/Human dual**
only — [North Star](/architecture/north-star.md) and
[Control & Escalation](/architecture/control-and-escalation.md) — with a strict on-demand-only teach
overlay, never a live third seat. A mode-line position that reads "AI" as a *driving* state is a
reborn-invariant violation on sight, on any surface, not a stylistic variance. Tip play shell
(PWO-060 · `2ca3154`) ships **App XOR Human** with an AST vocabulary gate; `[CODE DIVERGENCE]` the
archived build's `_MODE_BADGES` (`spectate_layout.py`) still carries an `ai_pilot → "AI-PILOT"`
entry at tone `info` — port-source only, do not revive.

### Per-cell game color is a distinct system

Inside the `[GAME UI]` viewport, `terminal.color_map()` (`terminal.py`) RLE-encodes pyte's true SGR
fg/bg/bold per row, and `_ColorPairs` (`spectate_app.py`) lazily allocates a curses pair per
distinct `(fg,bg)`, degrading to plain bold/normal when the pair table is exhausted. The viewport
therefore renders in the **server's own CP437 palette**, not the 7-tone semantic set — what the
operator sees is exactly what the game sends, reproduced, never reinterpreted. `[HYPOTHESIS]` The
stock-TradeWars convention that "red = hostiles, cyan = menu chrome" in that native palette is
**unverified** and must stay hypothesis-marked wherever a surface repeats it — never promoted to
fact without live introspection.

**Cut, deliberately:** no light theme (dark + high-contrast only). One table, seven meanings, one
selection attribute — the whole palette is monochrome-plus by design, not by omission.

## Glyph / status-marker vocabulary

Two parallel glyph tables — `GLYPHS_UNICODE` / `GLYPHS_ASCII` (`terminal.py`) — switch on a single
`unicode_ok` flag via `glyph_set()`, so every chrome element (border, spinner, heartbeat,
freshness/delta marks) degrades **together**, never per-glyph, and a non-UTF-8 terminal loses
fidelity but never meaning.

| glyph | ASCII twin | meaning | source |
|---|---|---|---|
| `✓` | `✓` (no swap) | met / known — a satisfied GOALS/FOCUS condition | `compose_primary_goals_lines` |
| `·` | `·` (no swap) | in progress / partial, or "other candidate" in a decision trace, or a header separator | `compose_primary_goals_lines` / `format_autopilot_trace_lines` |
| `?` | `?` (no swap) | unknown — an unresolved GOALS condition, an empty/unrecognized STOP reason code, or an unrecognized mode badge | `compose_primary_goals_lines` / `intervention_labels.py` / `format_mode_badge` |
| `⊘` | `⊘` (no swap) | blocked / gated — an unmet prerequisite, a gated autopilot-trace candidate, or `[ASPIRATIONAL]` a non-connectable catalog entry | `compose_primary_goals_lines` / `format_autopilot_trace_lines` |
| `✦` | `*` | freshness mark — **non-negotiable per `TUI-POLISH-PLAN.md`**; appears on every persisted value as `✦ Ns ago` / `✦ now`, dims past 20s | `format_freshness` |
| `★` | `★` (no swap) | centerpiece / you-are-here / chosen-action — the MENU MAP marker (`here ★{cur}`), the autopilot-trace chosen action, the longest Loops chain | `format_autopilot_trace_lines` / `menu_map_view.py` |
| `▸` | `▸` (no swap) | the selected/armed row marker (chains library) and the play-progress separator `Playing <name> ▸ cycle/total` | `spectate_app.py` |
| `→` | `→` (no swap) | sent-key / TX channel (`→ 158` sent, `→ -` idle) and the step arrow | `format_tx_readout` |
| `⇒` | `⇒` (no swap) | the LOG "landing differs" suffix | `spectate_layout.py` |
| `○ ○` | `○ ○` (no swap) | the empty-chain placeholder (`○ ○  no trade loop yet`) | `spectate_app.py` |
| `—` (em-dash) | `—` (no swap) | an unknown/empty value, in place of a fabricated `-` or a blank | throughout HUD/GOALS/PRIORITIES rendering |
| `×` | `×` (no swap) | dimensional multiply in gate/refusal copy (`C×L`, `60×20`) — same no-swap family as `·` / `—`; never ASCII `x` | `tw2002_aiclient/cockpit/layout.py::frame_layout` `too_small` `message` (≈97–102) |
| `!` | `!` (no swap) | leads the STOP / intervention strip — the one-glyph "attention" mark | `compose_intervention_strip` |
| `KEY)verb` | `KEY)verb` (no swap) | the uniform hotkey-token shape on the control-strip hint band (`^A)ode`, `A)nalyze`, …) | `spectate_app.py` control strip |

**Motion glyphs** (see the Liveness-cue catalog below for full behavior): spinner `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`
(ASCII `|/-\`) · heartbeat `●`/`○` (ASCII `*`/`.`) · sparkline `▁▂▃▄▅▆▇█` (ASCII `.-=#`) ·
fuel/bar-meter fill `█`/`░` (ASCII `#`/`.`) · delta chip `▲`/`▼` (ASCII `^`/`v`).

## Box-drawing / border hierarchy — the two-weight system

`terminal.py` defines a deliberate **two-weight** border system, switched by the same `unicode_ok`
flag so every glyph has an ASCII twin:

| element | Unicode | ASCII | weight |
|---|---|---|---|
| **viewport** corners/edges | `╔ ╗ ╚ ╝` `═` `║` | `+ + + + = |` | double-line |
| **HUD / all chrome** corners/edges | `╭ ╮ ╰ ╯` `─` `│` | `+ + + + - |` | thin rounded |

- **Double-line = the live game; thin-rounded = every instrument.** The heavier border is a focus
  signal — a deliberate BBS/DOS-door echo (`TUI-POLISH-PLAN.md` Phase 1). The eye lands on the
  CP437 world first; the rounded chrome frames it without competing.
- **Outer frame:** one double-line box around the *whole* client (`_draw_outer_frame`, cyan
  **bold**) — the unifier that makes a multi-panel surface read as one cockpit rather than several
  stacked widgets.
- **Viewport zero-inset is an invariant, not a style choice.** The `[GAME UI]` box is titled
  `" GAME "` with the border on row/col 0 and content at (1,1), **zero inner padding**
  (`_content_inset`, `spectate_app.py`). Any inward pad would shear the game's own CP437 box-art —
  this is why `VIEWPORT_W/H = GAME_W+2, GAME_H+2` (82×27, from `GAME_W, GAME_H = 80, 25`) and never
  a padded inset.
- **Titled thin boxes** carry their title at `addnstr(0, 2, " TITLE ")` in cyan — the uniform
  titling convention every instrument box on every surface follows (`HUD`, `LOG`, `DECISIONS`,
  `PRIORITIES`, `FORMATIONS`, `MENU MAP`, `TRADE LOOP CHAINS`, and `[ASPIRATIONAL]` a launcher's
  `PLAYERS`/`SERVERS` boxes).
- **Chain bubbles** are rounded `╭─╮ │ ╰─╯` joined by a heavy `═════` connector (`_CHAIN_CONNECTOR`,
  `spectate_layout.py`) — the one place a chrome element deliberately borrows the viewport's heavier
  weight, marking the trade loop as the "live" instrument.
- **No double-line weight exists outside a live game viewport.** A surface with no socket open (the
  launcher) never earns the heavier border — it is reserved exclusively for the CP437 world.

## Liveness-cue catalog — the "is it frozen?" killers

Animation is decoupled from content so motion never costs a redraw storm: chrome animates at
`ANIM_FPS = 13` (`spectate_app.py`, i.e. one repaint per ~77ms), the viewport redraws only on a real
settle-edge event, and a disconnected session drops to a slow `IDLE_ANIM_INTERVAL_S = 0.5s` idle
cadence. All flashes are `is_recent`-gated: they decay and never stick, so the steady state settles
back to quiet.

| cue | glyph / const | behavior |
|---|---|---|
| waiting spinner | braille ramp `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` (ASCII `\|/-\`) | advances while connecting/between events; frozen at frame `[0]` when calm |
| heartbeat | `●`/`○` (ASCII `*`/`.`), `HEARTBEAT_PERIOD_S = 0.8` | always breathing — slower than the spinner, so "alive" reads even on a settled screen |
| credit sparkline | `▁▂▃▄▅▆▇█` (ASCII `.-=#`), `CREDIT_SPARK_WIDTH = 20` | scaled to its own recent min/max; a flat series renders the middle glyph |
| turns fuel-gauge | `[████░░░░░░]`, `TURNS_GAUGE_WIDTH = 10` | green→amber→red via `gauge_semantic` as turns drain |
| delta chip + tween | `{delta:+,} ▲/▼`, `CREDIT_FLASH_DURATION_S = 1.5`, ~0.3s tween | slot-machine count-up on a credits change, then fades |
| ticker flash | newest LOG row bold, `TICKER_FLASH_DURATION_S = 1.0` | flags a just-arrived transcript line |
| classification pulse | header reverse-video, ~1.0s | pulses when the underlying screen classification changes |
| freshness stamp | `✦ Ns ago` / `✦ now` (ASCII `*`), `format_freshness`, `FRESHNESS_STALE_S = 20.0` | on every persisted value; dims to `A_DIM` past 20s without ever blanking |
| `→ TX` channel | `→ 158` sent / `→ -` idle, `format_tx_readout` | the live sent-keystroke readout; on Attach the same channel reads as `sent:{n} → {last}` |

The `→ TX` value is already redacted upstream — a `--secret` send arrives pre-masked from
`Session.send()`, so a password never reaches this channel; see
[Secrets & Credential Handling](/doctrine/secrets-and-credentials.md).

## Responsive-fold ladder

The fold is **cols-driven**, keyed on inner content-column budget (`frame_layout`,
`spectate_layout.py`; the constants below are measured against the 1-cell-inset inner size, a real
terminal's raw `cols` needs `+2`). Height degrades in a fixed order — header → control → ticker →
viewport border — before ever falling to `too_small`, and the intervention strip always claims
leftover height **first**, ahead of that ladder, so a halt banner survives even a height-starved
terminal.

| tier | inner-cols floor | constant | layout |
|---|---|---|---|
| `full` | ≥154 | `FULL_GUTTER_MIN_COLS` (`VIEWPORT_W+HUD_GUTTER_W+PRIORITIES_W`, 82+36+36) | PRIORITIES gutter (left) \| centered game \| HUD gutter (right) — both side gutters |
| `right_gutter` (wide) | ≥138 | `LEFT_GUTTER_MIN_COLS` (`VIEWPORT_W+HUD_GUTTER_W+PRIORITIES_MIN_W`) | bordered viewport (left-anchored) + right HUD; a narrowed left PRIORITIES (`PRIORITIES_MIN_W = 20`) still fits |
| `right_gutter` (narrow) | ≥118 | `RIGHT_GUTTER_MIN_COLS` (`VIEWPORT_W+HUD_GUTTER_W`) | bordered viewport + right HUD only, no left gutter |
| `minimal` | ≥82 | `MINIMAL_HEADER_MIN_COLS` (`== VIEWPORT_W`) | bordered viewport, centered, no side gutter — HUD rides the packed header strip |
| `no_border` | ≥60 | `MIN_COLS` | viewport border dropped, game full-bleed/clipped |
| `too_small` | <60 | — | refuses to render: `Terminal too small (C×L) — need at least 60×20` |

**Cockpit chrome tones (shipped tip `f594b9e` — DOC-GAPs closed through WO-P3-040):**

- **Row-1 profile strip** (`host · game-letter · handle`) is **data**, not chrome — render at
  default **`A_NORMAL`** (untinted, non-bold). Cyan stays on the outer frame / instrument borders
  only ("cyan is chrome, never data"). Code: `tw2002_aiclient/screens.py` PlayShellScreen.draw
  strip `draw_lines(..., curses.A_NORMAL)`.
- **`too_small` refusal** is a **gate statement**, not a warn/danger halt — tone **`info`
  cyan+bold** (same attr as the outer-frame chrome pair). Code: `screens.py` PlayShellScreen.draw
  `draw_refuse_message(..., self._outer_attr)` where `_outer_attr` is cyan|bold.
- **GAME viewport border danger (STATUS surface)** — when `connected` is a definite `False`,
  border attr is **red non-bold**: the surface overrides the shared `danger` row's bold bit so the
  link-down cue stays distinct from outer-frame bold cyan and from bold danger used elsewhere
  (credit-loss flash, live-play confirm). Honest-unknown / missing `connected` stays default cyan
  chrome (classifier only consulted on a real bool). Mono interim: **`A_UNDERLINE` non-bold**
  (see load-bearing rule above). Code: `cockpit/tones.py` + `screens.py` `_viewport_border_attr`.

`[CODE NOTE]` The **archived** `twclient/spectate_layout.py::frame_layout`'s own docstring ladder
comment states the `full` floor as `>=142`; the governing comparison actually gated in that code is
`i_cols >= FULL_GUTTER_MIN_COLS`, which computes to **154** from the module's own
`VIEWPORT_W/HUD_GUTTER_W/PRIORITIES_W` constants — the archived docstring number was stale relative
to the constant it describes. The table above states the constant-derived (behavior-governing)
value; the reborn port, `tw2002_aiclient/cockpit/layout.py::frame_layout` (PWO-031/033), now
encodes that `>=154` floor directly — the rebuild this note asked for has happened.

**Fold stack order below 138 (PWO-039 · tip `f594b9e`):** when the left gutter sheds, the
right-gutter **DECISIONS** pane hosts the folded stack — title stays **`DECISIONS`** — in fixed
order **trace → GOALS → FOCUS** (autopilot-trace lines unlabeled as the pane's own identity; then
a bare `GOALS` label + digest; then a bare `FOCUS` label + ranked lines). Height-clip is
**bottom-first**: FOCUS sheds before GOALS before trace. Code: `tw2002_aiclient/cockpit/fold.py`
`compose_folded_decisions_lines`.

**Graceful-collapse principle — applies on every surface, not just the cockpit:**

- **The body never scrolls horizontally.** Content that cannot fit is *folded*, never pushed off the
  right edge — a viewport stays ≤80(game)/82(bordered) wide, a LOG-style panel truncates to its
  line-tail, a chain bubble truncates left→right with a `… Nh` marker, a launcher's columns
  `[ASPIRATIONAL]` collapse to a single stacked row rather than overflow.
- **Panels shed by column budget in a fixed priority** (full gutters → narrow left gutter → right
  HUD only → bordered viewport alone → unbordered viewport), with secondary content (GOALS +
  FOCUS) folding *into* idle DECISIONS below 138 (stack order above) before either is dropped
  outright.
- **Degradation loses chrome and redundancy, never information.** The viewport — the live game
  itself — is always the last thing to survive a fold; unicode/ASCII glyph twins carry zero
  information loss by construction.
- **`too_small` refuses rather than renders broken.** Below the floor, the frame states the problem
  plainly (info cyan+bold gate copy — see Cockpit chrome tones above) instead of drawing a sheared
  layout.

## Aesthetic direction — the shared "feel"

**Dense-but-readable, terminal-native, calm-until-it-needs-you.** Every surface in the bundle aims
at the same north star: a single coherent composition (one outer double-line frame, cyan chrome
accent, the two-weight border hierarchy giving the live CP437 game visual primacy) that stays quiet
at steady state — a muted or green badge, a frozen spinner, no color noise — and escalates hard and
unmissably the instant something needs a human: a bold-yellow `!` strip that claims height ahead of
everything optional, or the loudest combination the palette owns (danger + reverse-video) at the one
place a keystroke could spend real money. Liveness is never silent — every persisted value carries
`✦ Ns ago` and a heartbeat breathes even on a settled screen, so nothing reads as frozen when it is
merely calm. The system never lies or invents: an unknown renders `?` / `—` / `off-map`, a gated
action wears `⊘`, an empty panel states its emptiness honestly rather than vanishing. Degradation is
always with dignity — glyph twins losing zero meaning, panels folding by budget, a body that never
scrolls sideways — and the whole stack is hand-built on pure stdlib `curses` with zero added
packages (`rich`/`textual`/`blessed` deliberately rejected); the anti-gold-plating discipline (no
light theme, no powerline separators, no pane intro-stagger, no full-grid marquee) is itself part of
the taste, not an omission (`TUI-POLISH-PLAN.md`).

# Examples

## A calm cockpit reading (App healthy, nothing to see)

```
[ APP ]      → 158                         ^A)ode  A)nalyze  R)ecord  T)rigger  L)chains  P panic
  ^ green, reverse-video chip     ^ uncolored TX telemetry    ^ cyan chrome hint band, right-aligned
```
No intervention strip is drawn; the spinner is frozen at frame `[0]`; only the heartbeat and the
freshness stamps move.

## A STOP escalation (the loudest non-money moment)

```
! autopilot_no_candidates
```
Rendered warn-tone (yellow) **and** bold, one row, led by a bare `!`, pinned directly above the
status bar — claiming leftover height ahead of the control strip and ticker.

## The one money-path confirm (the loudest moment, period)

```
Play "Ferren-Sol" x3 LIVE? y/N
```
Drawn `danger`-tone (red/bold) **and** reverse-video simultaneously — the only place in the bundle
the loudest tone and the selection attribute combine — because it is the only place one keystroke
could commit live turns. `y/N` capitalization signals the safe default; a bare Enter never fires.

# Citations

- **Color semantics, mode badges, per-cell game color** — `spectate_app.py` (`_SEMANTIC_COLORS`,
  `_PYTE_TO_CURSES_COLOR`, `_ColorPairs`, `_tone_attr`, `ANIM_FPS`, `ANIM_INTERVAL_S`,
  `IDLE_ANIM_INTERVAL_S`, `HEARTBEAT_PERIOD_S`), `spectate_layout.py` (`status_semantic`,
  `gauge_semantic`, `_MODE_BADGES`, `format_mode_badge`), `terminal.py` (`color_map`).
- **Glyphs, box-drawing, two-weight border hierarchy** — `terminal.py` (`GLYPHS_UNICODE`,
  `GLYPHS_ASCII`, `glyph_set`), `spectate_app.py` (`_draw_outer_frame`, `_content_inset`),
  `spectate_layout.py` (`_CHAIN_CONNECTOR`, `compose_primary_goals_lines`,
  `format_autopilot_trace_lines`, `format_freshness`, `format_tx_readout`,
  `compose_intervention_strip`).
- **Liveness-cue constants** — `spectate_layout.py` (`FRESHNESS_STALE_S`, `CREDIT_FLASH_DURATION_S`,
  `TICKER_FLASH_DURATION_S`, `CREDIT_SPARK_WIDTH`, `TURNS_GAUGE_WIDTH`, `render_sparkline`,
  `render_bar_meter`).
- **Responsive-fold ladder** — `spectate_layout.py` (`frame_layout`, `GAME_W`/`GAME_H`,
  `VIEWPORT_W`/`VIEWPORT_H`, `HUD_GUTTER_W`, `PRIORITIES_W`/`PRIORITIES_MIN_W`,
  `MINIMAL_HEADER_MIN_COLS`, `RIGHT_GUTTER_MIN_COLS`, `FULL_GUTTER_MIN_COLS`,
  `LEFT_GUTTER_MIN_COLS`, `MIN_COLS`, `MIN_LINES`); reborn port
  `tw2002_aiclient/cockpit/layout.py::frame_layout` (incl. `×` in `too_small` message).
- **Cockpit strip / refuse / viewport-STATE tones (tip `f594b9e`)** —
  `tw2002_aiclient/screens.py` PlayShellScreen (`A_NORMAL` row-1 strip; `_outer_attr`
  cyan+bold on `draw_refuse_message`; `_viewport_border_attr` red non-bold /
  mono `A_UNDERLINE`); `tw2002_aiclient/cockpit/tones.py` (`SEMANTIC_COLORS`,
  `status_semantic` / `gauge_semantic`).
- **Folded DECISIONS stack (tip `f594b9e`)** — `tw2002_aiclient/cockpit/fold.py`
  `compose_folded_decisions_lines` (trace → GOALS → FOCUS; height-clip bottom-first).
- **Consuming surfaces (the sentences to this dictionary)** —
  [The Trainer Cockpit](/surfaces/trainer-cockpit.md),
  [Mode Line & Teach Controls](/surfaces/mode-line-and-teach-controls.md),
  [Spectate & Attach](/surfaces/spectate-and-attach.md),
  [Entry & Profile Selection](/surfaces/entry-and-profile-selection.md) — each states this
  vocabulary's *application*, never a competing definition of it.
- **The App/Human-only control dual (no AI-drives mode)** —
  [North Star](/architecture/north-star.md),
  [Control & Escalation](/architecture/control-and-escalation.md).
- **Redaction of the `→ TX` channel** —
  [Secrets & Credential Handling](/doctrine/secrets-and-credentials.md).
- **Polish intent, cut list, BBS/DOS-door echo, dark-only theme** — `TUI-POLISH-PLAN.md`.
- **Rebirth code location** — most cited symbols still live under
  `archive/pre-rebirth-2026-07-23/code/twclient/`; reborn cockpit frame symbols cited above
  (`cockpit/layout.py`, PlayShellScreen strip/refuse tones) live at tip under `tw2002_aiclient/`.
