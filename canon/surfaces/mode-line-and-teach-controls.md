---
type: System
title: Mode Line, Teach Hotkeys & the Escalation Handoff (UX)
description: The cockpit interaction contract — the App/Human actor indicator, the Ctrl-A Mode chord and A/R/T keys, the operate-the-app control cluster, and how STOP-and-handoff is presented to the human.
tags: [surface, mode-line, teach-controls, escalation-handoff, human-approval, confirm-gate, prescriptive]
timestamp: 2026-08-06T01:46:00Z
---

This is the cockpit's **interaction contract**: the small band of always-visible chrome that tells
the human *who holds the keyboard right now*, the keys that let the human switch control and teach
the app, the cluster of controls that operate the app's autopilot, and the banner that presents a
STOP-and-handoff when autopilot meets a screen it cannot match. It owns **presentation**, not
mechanics — the control state machine and the escalation reason-code catalog belong to
[control-and-escalation](/architecture/control-and-escalation.md), which this surface renders from
and defers to. This concept is prescriptive: it specifies the reborn dual-actor mode line, the teach
loop the A/R/T keys drive, and the confirm-gated control cluster the trainer targets, and it records
where the current code still carries the pre-reborn "AI drives" framing.

## Trainer strip amendment — DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` (2026-07-31, `WO-PLAY-STRIP-TRAINER-CHROME`)

Max ruled a **trainer-specific calm band and seat chip** for this product's Play cockpit,
superseding the developer-repertoire calm-band diagrams below for THIS surface. The underlying
A/R/T teach-loop mechanics, the STOP banner's own `teach:` line, and the confirm-gate are all
**unchanged** — only the trainer's own calm-band CHROME and seat-chip wording change:

- **Seat chip merges Mode + ARM.** The trainer's mode chip reads `^A)APP-ARMED` /
  `^A)MANUAL-HUMAN` (narrowing to `^A)APP` / `^A)MANUAL` under width pressure) instead of a bare
  `APP`/`MANUAL — YOU HAVE CONTROL` chip beside a separate `ARM ON`/`ARM OFF` chip — "App holding
  the seat" reads as armed-by-default for this trainer model (DECISION point 6: "App-armed auto =
  default"). **Spectate is never remapped** — it stays the honest, unarmed `SPECTATE` reading; no
  ARM claim is ever attached to a non-seat-holding viewer.
- **Calm band retires A/R/T/V/U, `H)old?`, `O)ffer?`, and `P panic`** in favor of a trainer-plain
  vocabulary: `E)xplore  F)ind StarDock·ON  P)ort Trade·ON  C)argo Hold Upgrade·ON  S)hip Upgrade·ON  │  T)rade Loop Chain  L)ist Loops` (P/C/S default **ON**; `·` is this doc's own NO-SWAP glyph, same convention as
  the `KEY)verb` rule below). The retired tokens' underlying features (Analyze, Record, reflex, the
  rules library, the hold/offer confirm gates, the Trade-Loop-Chains popup, panic) are **all still
  reachable by their existing keys** — only the standing chrome that advertises them on THIS calm
  band changes. The STOP banner's own escalation `teach:` line is tip
  `A)nalyze  R)ecord` only (no false `T)assign` after calm `T` → Trade Loop) —
  a different surface, not this calm band.

**Tip token SSOT (do not let chrome and handlers drift).** Calm-band spellings and the keys that
offer them are owned by tip modules — import the `*_TOKEN` / help strings; do not re-type labels:

| Concern | Module | Load-bearing symbols |
|---|---|---|
| Standing calm teachband chrome | `tw2002_aiclient/cockpit/teachband.py` | `compose_teach_band`, `TEACH_TOKENS` (imports below) |
| Explore / policy / Mode / L·T help | `tw2002_aiclient/cockpit/autonomy_keys.py` | `EXPLORE_TOKEN`, `compose_autonomy_help_lines`, `MODE_HELP` … |
| Reflex offer (retired from *calm* chrome; key still live) | `tw2002_aiclient/cockpit/reflex_controls.py` | `REFLEX_TOKEN` (`V)reflex`), `REFLEX_OFFER_KEYS`, `compose_reflex_confirm_action` |
| Loops popup spelling | `tw2002_aiclient/cockpit/chains.py` | `CHAINS_TOKEN` (re-exported as List-Loops on the calm band) |

`teachband` imports `REFLEX_TOKEN` / `EXPLORE_TOKEN` / `CHAINS_TOKEN` so the strip and the key
handler cannot disagree on a label — same pattern as `panic.PANIC_TOKEN`. A future edit that
"tidies" a TOKEN string in one module only is a defect.

*(Honesty pass `AUDIT-CANON-DRAFT-TEACH-BAND-CROSSREF`, 2026-08-04.)*

- **CONN moves to the profile/title strip**, beside the host identity, as a slow-flash green `●`
  while connected (offline/unknown stays honest non-green, never a lying pulse) — it no longer
  renders on this bottom control strip.
- **`status_line` / outcome prose routes into LOGS**, not a mid-control-strip segment — the
  control strip carries only the seat chip, the coverage meter, the calm band, and the liveness
  cluster.

Code waves: `WO-PLAY-STRIP-TRAINER-CHROME` (this amendment, chrome only) →
`WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS` (left-gutter layout) → `WO-PLAY-STRIP-POLICY-AUTO` (wires
the P/C/S toggles + the App-armed-auto policy this amendment's chrome only advertised at the time).

### Policy-auto amendment — `WO-PLAY-STRIP-POLICY-AUTO` (2026-07-31, DECISION point 6)

The chrome above is now backed by real behavior, not just a rendered `·ON`/`·OFF` suffix:

- **Mode-leave IS the halt.** `^A` from `APP-ARMED` to `MANUAL-HUMAN` stops every live App
  runner (explore, the taught autoloop, the trade-chain, and the StarDock hold-buy) before the
  human takes the seat — "leave App → Manual" (DECISION point 1), making STOP/PANIC redundant as
  a separate operator control on this calm path. The retired `P panic` binding (above) stays
  retired; `cockpit/panic.py`'s own halt verbs are unchanged and reused, plus a fourth
  (`stardock_hold_stop`) this Mode-leave halt adds that panic itself never covered.
- **Two modes (RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES, Max 2026-08-01).**
  - **`E)xplore`** — discovery mode: StarDock, formations, planets, **map / learn** Trade Loop
    Chains. Docking under Explore is world-model sampling only — not Trade Loop execution.
  - **`L)ist Loops`** — selects which discovered/taught loop is **armed** for execution.
  - **`T)rade Loop Chain`** — start/stop **execution** of the L-armed loop (warp to start → trade
    each port). Label must match behavior (not legacy Assign-Trigger).
  - **`P)ort Trade·ON`** — money gate for Trade Loop **execution** only. It does **not** control
    Explore gather docks (`dock_new_ports` is Explore’s discovery concern, decoupled from P).
    Play defaults and the deliberate `dock_new_ports` vs `fight_tolls` asymmetry live in
    [exploration-policy](/strategy/exploration-policy.md) § Play explore flags
    (`AUDIT-CANON-DRAFT-EXPLORE-FLAGS-ASYMMETRY`).
- **`C)argo Hold Upgrade·ON` gate a real App-armed auto-fire** for hold-buy when APP-ARMED and the
  toggle is ON (unchanged by the Explore/Trade split). Manual fallbacks remain sovereign.
- **Trade Loop execution is not silent FOCUS auto-fire during Explore.** Under APP-ARMED +
  `P)ort Trade·ON`, **`T`** runs the L-armed loop without per-action `y` (trainer default). The App
  must not pick a FOCUS bubble chain and spend money while Explore owns discovery.
- **`S)hip Upgrade·ON` gates nothing yet, honestly.** No ship-upgrade engine or offer kind exists
  in this codebase, so the toggle is local-only chrome by necessity, not an unwired follow-on —
  the honest state until a future WO lands a real ship-upgrade path to gate.

# Schema

## The mode line is a DUAL, not a triad

The live keyboard is held by exactly one of **two** actors — **App** or **Human** — and the mode
line shows which. There is **no third "AI drives" position.** The reborn trainer has exactly two
live keystroke senders (`app`, `human`; see [trace-ledger](/engine/trace-ledger.md)); the AI is a
retrospective, human-invoked *teacher* and never a live driver (see
[ai-teacher](/engine/ai-teacher.md)), so it can never be the actor the mode line names.

- **App** — the deterministic autopilot holds the keyboard and is playing only taught screens. It
  stops and hands back the instant it meets an unrecognized screen. **Chip text = `APP`** (Max
  Batch 2/3 docs-win; shipped `APP_LABEL="APP"`) — actor prose may still say App.
- **Human** — the human holds the keyboard directly (the live `tw attach` seat). Sovereign; the app
  does not drive while Human holds control.

The AI never appears *as a mode.* It surfaces only as a transient **teach-overlay indicator** — a
badge shown while an Analyze (teach) pass is open — never as a control-line position and never
implying the AI is on the wire. A read-only **Spectate** viewer is not a Mode and not a control
holder: it takes no lock and drives nothing (see [spectate-and-attach](/surfaces/spectate-and-attach.md)),
so it does not occupy the App/Human dual. Default when the client runs = App/autopilot. **Ctrl-]
from App-hold = deliberate no-op stay App** (Max Batch 2/3; do not invent a Spectate transition).

## `Ctrl-A` — the App↔Human Mode switch

**Ctrl-A** is the Mode chord (ADR-002): it toggles the live holder between **App** and **Human**.
No single printable may be Mode. While Human is attached, bare `M` is TW Move (passthrough), not
Mode. Switching **to Human is immediate and unrefusable** — the human always wins the keyboard the
instant they ask for it, even mid-dispatch; a taught behavior caught mid-flight is fenced and yields
cleanly rather than being interleaved. This is a presentation summary only; the guarantee and its
clean-cutover mechanics live in [control-and-escalation](/architecture/control-and-escalation.md)
and the control-lock. The mode line reflects the new holder the moment the switch lands.

## The teach hotkeys — A / R (and calm T)

At an escalation moment (or any time the human wants to grow the repertoire),
the teach / operate keys on this surface include:

- **`A` — Analyze.** Invoke the retrospective [AI teacher](/engine/ai-teacher.md) on the current
  screen / escalation moment. The teacher reads the settled screen, parsed state, and surrounding
  ledger *after the fact* and returns a **draft** guarded rule for the human to approve, edit, or
  discard. On-demand only — the AI never proposes unless the human presses `A`. While a pass is open,
  the teach-overlay indicator shows on the mode line. **Tip:** `PlayShellScreen` → `analyze_open` /
  `analyze_close` (WO-P5-069); printable `A` is **not** attach (Mode is Ctrl-A).
- **`R` — Record.** Capture a [macro](/engine/macros.md): record the human's own keystroke
  demonstration as a replayable taught sequence. The captured macro is the `do` a rule will later
  play. **Tip:** `record_toggle` (WO-P5-067).
- **Calm `T` — Trade Loop Chain** (Max DECISION · WO-EXPLORE-TRADE-MODE-SPLIT). Starts/stops the
  L-armed Trade Loop (`trade_loop_toggle`). This is **not** Assign-Trigger on the calm path.
  Confirm preview identity for a discovered chain comes from tip
  `trade_chain_plan.py` (`TradeChainPlan` / `compose_confirm_action`) — see
  [trade-loops § Discovered → approved semantic plan](/strategy/trade-loops.md#discovered--approved-semantic-plan-adr-003);
  calm `T` never itself invents a fingerprint or send path.
- **Assign-Trigger** (bind screen-match + guards → proposed rule) remains a tip module
  (`cockpit/assign_trigger.py` + `app.py` handler for non-calm / programmatic callers such as
  draft-approve). Calm `T` is Trade Loop; the STOP banner teach line is
  **`teach:  A)nalyze  R)ecord` only** (no false `T)assign`).
  **Calm-band disposition (hub 2026-08-06 · WO-BUILD-ASSIGN-TRIGGER-REKEY):** Assign-Trigger is
  **retired from the calm band**, not remapped to a new letter — Max's explore/trade-loop ruling
  already excludes it from the retired-tokens keep-list (Analyze, Record, reflex, rules, hold/offer,
  panic). Backend + handler stay for non-calm entry points; do not invent a calm key.


Analyze / Record proposals remain **proposals, never live keystrokes.** Every proposed rule
surfaces an **approve/reject** affordance and is **inert until the human approves it**.
AI proposals exist only because the human pressed `A`.

## The operate-the-APP control cluster (N5)

The controls that *operate the app's autopilot* all live on this surface — the
[trainer-cockpit](/surfaces/trainer-cockpit.md) only renders them in its frame; the behavior contract
is owned here. The cluster is:

- **The mode selector** — the Ctrl-A App↔Human Mode switch above.
- **Run / record / panic / pause controls** — launch a taught run, record a macro (`R`), a **panic**
  control that halts *all* automation and parks the app in a non-driving paused state, and a
  **Space pause** that parks a taught AUTO-LOOP without spending (see Pause & relaunch below). What a
  run and a panic actually arm and halt is [app-autopilot-model](/architecture/app-autopilot-model.md);
  this surface owns how they are presented and gated.
- **The Trade-Loop-Chains library popup** — a modal listing the taught trade-loop chains the human
  can launch (see [trade-loops](/strategy/trade-loops.md)); selecting a chain arms a launch.
- **The blessed rules peek (`U)rules`)** — read-only overlay of the approved rule library (see
  below). Peek only: no arm, promote, or send path.
- **The play-launch confirm** — see the confirm-gate below.
- **Whole-app exit confirm** — `q` that would exit the **client process** (from Play, or after a
  bank/launcher quit routes here) raises **"Stop daemon and disconnect \<profile\>? y/N"** before
  the process ends. Same **key posture** as the arm confirm (`y`/`Y` only; Enter/Esc/non-`y` =
  default No = quit client, leave daemon). This is **not** a money-path arm: semantic confirm
  styling is fine; do **not** reuse LIVE / turn-spend wording or any direct-send path. Esc that
  only returns to the launcher is outside this cluster — it must issue **zero** `stop` traffic.
  Exact popup ownership for Play chrome lives with this surface's N5 contract; the launcher hosts
  the same dialog when `q` is pressed there (one app-lifecycle bookend, two entry points).

### Blessed rules peek (`U)rules`) — read-only library (shipped)

Tip: `cockpit/rules_library.py` + `PlayShellScreen` (`U`/`u` toggle). Same overlay idiom as Analyze /
Chains — never auto-opens. Drafts never appear; the caller passes the blessed `rules` list only
(`include_drafts=False`).

**Store statuses** (branch on `read_rule_store` `status` before claiming a count — an empty
`rules` list is true for absent, empty-ok, and unreadable):

| Status | Operator sentence (tip copy) |
|---|---|
| `ok` with rows | Scrollable list: `rule_id`, `do`, `screen_match`, `prio`, `scope` (`one-shot`/`repeating` or `?`) |
| `ok` empty | `no blessed rules yet` |
| `absent` | `rule library absent — nothing written yet` |
| `unreadable` | `rule store unreadable — cannot list` |
| `partial` | Banner `PARTIAL — some rule files unreadable`; lists what parsed, or the unreadable empty line if none |

**Cursor / dismiss.** While open, cursor owns scroll (`▸` / `>` selected row). Toggle `U` again or
the shared dismiss-first posture closes the peek — never arms a rule from this panel.

### Confirm-gate — never one keystroke to live money

**Arming a rule or launching a run is confirm-gated.** No single keystroke ever commits the app to
spend live turns or credits: selecting a chain or launching a run **arms** a pending action and
raises an explicit confirm prompt (a `y/N`-style gate that shows what will run and how many cycles);
only a deliberate second confirm fires it. A bare Enter must never fire a launch. This is a
non-negotiable money-path safety rule born of the **−75/−78-turn scars** — verified misfires where an
unguarded live action burned turns — and it applies to every arm/launch affordance in the cluster.
The FOCUS panel and any coaching suggestions are **ranked suggestions, never the app's chosen
action**: they inform the human, they do not arm or launch anything (see
[coaching-engine](/engine/coaching-engine.md)).

### Pause (Space) & relaunch (G) — taught AUTO-LOOP (shipped)

These keys operate the **taught AUTO-LOOP runner** already live on tip
(`cockpit/autoloop_controls.py`, daemon wire `autoloop_pause` / `autoloop_relaunch`). This section
documents existing confirm-gated behavior — it does **not** authorize a new money path.

- **Space — pause (ungated).** Halts further sends from the taught run and parks it. Pause spends
  nothing, so it shares panic's "confirm protects the direction that spends" posture: no `y/N`
  gate. Tip status copy: `paused — taught run parked (Ctrl-A to drive, G to relaunch)`.
- **G / g — relaunch offer (confirm-gated).** Offers a relaunch of the *paused* run. There is **no**
  `resume` / `autoloop_resume` on this surface or on the wire (hub ruling 2026-07-27, options 1+3):
  `replay_loop` has no start index, so re-arming always replays the macro **from step 1** and
  **re-issues sends already made**. Naming it "resume" would be a lie; the confirm line must say
  **Relaunch**.
- **Disclosure is load-bearing.** The daemon response (and the cockpit preview before confirm)
  carries `replays_from_start: true` and `sends_already_issued`. The confirm action text states
  that meaning in prose (`Relaunch — replays from the beginning, N sends already issued`), then
  the shared arm-confirm suffix (`LIVE?  y/N`). `sends_already_issued` is `None` when the player
  never produced a count — that is **unknown, not zero**, and must render as `?`, never as
  `"0 sends already issued"`.
- **Strict preconditions.** Relaunch is refused when nothing was deliberately paused (`not_paused`
  — a panic/stop is not relaunchable), when no macro name remains (`no_resumable_run`), or when
  the runner is unavailable. Only `y`/`Y` fires; Enter/Esc/non-`y` default-deny.
- **Not a shell `tw` verb.** Wire verbs exist; there is no `tw autoloop` CLI wrapper — see
  [cli-verbs](/architecture/cli-verbs.md) Implementation status.

## The STOP banner — a typed reason, keyboard→Human, and the three moves

When autopilot meets a screen it cannot match, it STOPs and hands the keyboard to the human. This
surface presents that handoff as a banner that carries:

- **A typed reason code**, not free text. The banner renders the escalation's reason *code* resolved
  through the enumerated catalog owned by
  [control-and-escalation](/architecture/control-and-escalation.md) and implemented as
  `INTERVENTION_REASON_LABELS` / `intervention_reason_label()` in `cockpit/stopbanner.py` — the
  banner shows the code's short human label, never an ad-hoc string. (The catalog is open by
  construction: an unrecognized code passes through as its own text, an empty code renders `"?"`.)
- **Keyboard → Human.** The banner makes explicit that control has passed to the human — the mode
  line reads Human — so the human is unambiguously the pilot.
- **The wired teach moves as affordances.** `A` / `R` are surfaced right at the STOP so the
  human can immediately Analyze or Record to teach the screen that caused the halt —
  turning the escalation into a durable rule for next time. Assign-Trigger stays a tip module
  for non-calm callers but is **not** advertised on the STOP teach line (calm `T` is Trade Loop;
  hub 2026-08-06 · WO-BUILD-ASSIGN-TRIGGER-REKEY — no replacement calm letter).

## The coverage / auto meter — App-vs-Human live share

The autonomy meter reports the **App-vs-Human live share**: of the live keystrokes/dispatches, how
many the taught App handled versus how many the Human had to. This is the honest measure of how much
of the *known* the app covers today (see [coverage-metrics](/engine/coverage-metrics.md)).

**Any "AI" figure is a distinct TEACHING axis** — rules authored and approved — **never a live-drive
share.** The AI's live keystroke share is definitionally **zero**, because the AI never drives. The
meter must not present the AI as a third live-drive slice competing with App and Human; a
teach-provenance number, if shown, is labeled and kept separate from the live share.

# Examples

## Mode line, healthy autopilot

```
[ APP ]  → K            AUTO 82%   App 41 / Hum 9        ^A)ode  A)nalyze  R)ecord  L)chains  P panic
```
The App holds the keyboard (dual: App or Human). The auto meter is App-vs-Human live share. No AI
slice appears in the live share; the teach keys sit on the hint band.

**Trainer surface (this product's Play cockpit, per the amendment above):**

```
^A)APP-ARMED   COV ?                E)xplore  F)ind StarDock·ON  P)ort Trade·ON  C)argo Hold Upgrade·ON  S)hip Upgrade·ON  │  T)rade Loop Chain  L)ist Loops  → K
```
The merged Mode+seat chip reads `^A)APP-ARMED` (App holding the seat under this trainer's
armed-by-default model); the calm band shows the six trainer tokens instead of the developer
A/R/T/V/U/H/O/L/P repertoire above. `CONN` is not on this row — it moved to the profile/title
strip beside the host identity (see the amendment above; the profile strip itself is
[trainer-cockpit](/surfaces/trainer-cockpit.md)'s own territory, not this surface's).

## The STOP-and-handoff banner

```
! STOP — autopilot halted            [ HUMAN — YOU HAVE CONTROL ]
  reason: autopilot no candidates    keyboard handed to you
  teach:  A)nalyze this screen   R)ecord a macro
```
The reason is a typed code (`autopilot_no_candidates`) resolved to its short label; the mode line has
flipped to Human; wired teach moves (Analyze / Record) are offered as affordances on the halt.
Assign-Trigger is not advertised here until it has a non-colliding key again.

## Launching a taught run — the confirm gate

```
TRADE LOOP CHAINS
  ▸ Ferren-Sol x3 (4 hops)
  ─────────────────────────
  Play "Ferren-Sol" x3 LIVE?  y/N        ← armed; a bare Enter does NOT fire
```
Selecting the chain *arms* a pending launch and raises an explicit `y/N` confirm. Only a deliberate
`y` commits live turns — never one keystroke to live money.

# Visual design & polish

This section specifies the **look** of the interaction contract — the mode-line chip, the teach-hint
band, the STOP banner, and the confirm-gate dialog — as a builder-aimable spec. Every concrete color
and glyph is grounded to a module (or marked `[ASPIRATIONAL]` where it is reborn-intent not-yet-built).
The color/glyph/border **dictionary** is shared across all four cockpit surfaces; this doc states the
mode-line-specific slice inline and forward-references the shared concept
[visual-language](/surfaces/visual-language.md) (authoritative shared vocabulary — tip).

## Color semantics — the mode indicator, teach overlay, and the one 7-tone table

Every tint on this surface resolves through the single semantic table `SEMANTIC_COLORS` /
`_SEMANTIC_COLORS` (`tw2002_aiclient/cockpit/tones.py` — tip; archive `spectate_app.py` port-source)
— one table, one meaning per tone on every surface. The seven tones:
`ok` = green/**bold**, `warn` = yellow/**bold** (pyte names it `"brown"` but it renders ANSI-yellow),
`danger` = red/**bold**, `info` = cyan/non-bold, `gain` = green/**bold**, `loss` = red/**bold**,
`muted` = terminal-default/non-bold (genuinely uncolored — basic-8 has no grey). **Cyan is chrome,
never data;** **reverse-video (`A_REVERSE`) is the single "selected / active / badge" signal** across
the whole UI.

**The mode-indicator colors** (tip `cockpit/control_seat.py` dual chips; archive `_MODE_BADGES` in
`spectate_layout.py` is port-source). Drawn reverse-video + tone-tinted on the control strip
(`compose_control_strip_segments` → `screens.py` draw). The badge is a reverse-video chip so it
reads as a chip, not text; the tone colors the chip:

- **App (autopilot holds the keyboard)** — **green (`ok`)**. Green is "healthy / the taught app is
  covering the known." Tip play shell (PWO-060 · `2ca3154`) ships the unified **`APP`** chip at
  tone `ok` + bold + reverse; archive still has two badges (`AUTO-LOOP` + legacy `AI-PILOT`) as
  port-source only — do not revive the cyan AI-PILOT badge.
- **Human (the live `tw attach` seat holds the keyboard)** — **yellow (`warn`)**. The as-built label
  is `MANUAL — YOU HAVE CONTROL` at tone `warn` (+ bold + reverse on tip dual). Yellow is deliberate,
  not an error: with the human flying, autopilot is stood down and the surface is in its
  *attention-with-you* register — the human, not the app, is the one thing that must not be ignored.
- **The teach-overlay (AI) indicator** — **cyan (`info`)**, non-bold. `[ASPIRATIONAL]` — the reborn
  teach badge shown *only* while an Analyze pass is open. Cyan places it firmly in the chrome/neutral
  register: it is an overlay annotation, never a live-drive slice, and its non-bold cyan visually
  separates it from the bold App/Human live-holder chips. It appears and vanishes with the pass.
- **Spectate (not a dual member)** — **muted / plain** (`spectate` → tone `muted`). A read-only viewer
  takes no lock, so its chip is deliberately uncolored — "nothing to see here," idle/parked, drawn
  reverse-video like every badge but with no bold accent next to the App/Human chips.
- **Trainer merged seat+ARM chip (amendment above)** — same `ok`/`warn` tones as the base App/Human
  chips (`^A)APP-ARMED` green, `^A)MANUAL-HUMAN` yellow), just with the Mode chord and the ARM
  reading folded into the one label instead of a second co-rendered `ARM ON`/`ARM OFF` chip.
  `^A)APP-ARMED`'s "ARMED" half is this trainer's own client-side default reading (DECISION point
  6), not a second daemon-verified fact the way the retired ARM chip was.

## Box-drawing, borders & titles

The mode line and its neighbors ride **thin rounded HUD chrome** (`╭ ╮ ╰ ╯ ─ │`, cyan;
`cockpit/draw.py` `THIN_*` / `unicode_ok`), the lighter of the two-weight hierarchy — the heavier
double-line `╔═╗` box is reserved for the live GAME viewport so the eye lands on the CP437 world
first. The control strip itself is a single unbordered row (no box) sitting inside the outer
double-line cyan frame; the **STOP / intervention strip** is likewise an unboxed single row led by
a bare `!`. The **Trade-Loop-Chains library** is a titled modal that *replaces* the dashboard
(tip chains/arm under `cockpit/`; archive `_draw_loops_library` in `spectate_app.py` port-source),
title drawn at col 2 in the shared cyan-title
convention; its confirm line is an inset row inside that modal. Every glyph has an ASCII twin via
the `unicode_ok` flag — an 80-col non-UTF-8 / `TW2002_ASCII=1` terminal loses fidelity, never
information.

## Spacing, alignment & hierarchy — the mode-line reading order

The control strip lays out strictly **left-to-right** (`cockpit/control_seat.compose_control_strip_segments`
→ `screens.py` draw; archive `compose_control_strip` / `_draw_control_strip` port-source):

```
[ APP ]      → 158                         ^A)ode  A)nalyze  R)ecord  L)chains  P panic
└ chip ┘     └ TX readout ┘                └──────────────  hint band (right-aligned) ──────────────┘
```

1. **The mode chip is cell #1, hard-left** — *who holds the keyboard* is the highest-priority fact on
   the strip, so it reads first, as a colored reverse-video chip.
2. **The `→ TX` readout** (`format_tx_readout`) sits immediately right of the chip in the strip's normal
   attribute (`A_NORMAL`, uncolored) — `→ 158` for the last sent keystroke, `→ -` when nothing is in
   flight. It is the live "the app just pressed a key" channel, kept low-key (no tint) so it registers
   as telemetry, not alarm.
3. **The hint band is right-aligned** in **cyan** (`accent_attr`), the chrome accent — it is
   affordance chrome, not data, so it wears the chrome color and yields the strip's center to the TX
   channel. When a taught run is live, the band's slot is claimed instead by the AUTO-LOOP
   cycle-progress bar (`Playing <name> ▸ cycle/total [███░░]`) — never both, there is only room for one.

The reborn hint-band *shape* is still `KEY)verb` with **Ctrl-A** as Mode (ADR-002 — no printable
`M)ode`). Tip no longer ships a `CONTROL_HINTS = "M)ode …"` constant; that archive string is gone
from product Python. Mode lives on the chip as `^A)APP-ARMED` / `^A)MANUAL-HUMAN` (narrows under
width pressure); the calm explore/goals band is composed separately (below).

**Trainer surface (tip):** the mode chip already carries the `^A)` chord
(merged into `^A)APP-ARMED`/`^A)MANUAL-HUMAN`), and the hint band is
`E)xplore  F)ind StarDock·ON  P)ort Trade·ON  C)argo Hold Upgrade·ON  S)hip Upgrade·ON  │  T)rade Loop Chain  L)ist Loops`
— every token still uses the same uniform `KEY)verb` shape (P/C/S additionally carry a `·ON`/`·OFF`
toggle suffix).

## The A / R / T / Mode hotkey affordances

The four keys are surfaced as `KEY)verb` tokens on the hint band and — at a STOP — promoted to the
banner's teach line. Their affordance styling:

- **Ctrl-A (`^A)ode`)** leads the band (the Mode switch is the strip's own primary control, adjacent
  to the chip it flips). A press flips the chip color the instant the switch lands (green↔yellow) —
  the color change *is* the acknowledgement. Attached bare `M` is Move, not Mode.
- **`A` / `R`** are the wired teach pair on the STOP banner's dedicated **`teach:`** line
  (Analyze / Record). Assign-Trigger is not a third calm/STOP letter after calm `T` → Trade Loop
  (WO-BUILD-ASSIGN-TRIGGER-REKEY). On the calm band the trainer tokens differ (see Policy-auto /
  tip token SSOT); on the banner `A`/`R` inherit the banner's warn-bold weight.
- Every affordance that *arms or launches* (a chain launch, a run) is confirm-gated (below) — the hint
  token merely opens the gate; it never fires.

## The STOP / escalation banner styling

When autopilot halts, tip `cockpit/stopbanner.py` paints the STOP banner from typed intervention
reason codes (archive `compose_intervention_strip` / `_draw_intervention_strip` in
`spectate_layout.py` / `spectate_app.py` remain port-source). The banner is **warn-tone (yellow) and
BOLD**, one row, **led by a bare `!`**, pinned **directly above the status bar**. The strip is
allocated *only* when intervention needs attention, and it **claims leftover height first** — before
the control strip, before the ticker — so a halt always surfaces even as the terminal shrinks
(`cockpit/layout.py::frame_layout`; archive `spectate_layout.frame_layout` port-source). This is the
concrete "calm-until-it-needs-you" mechanism: steady state shows no strip at all; a halt muscles a
bold-yellow row ahead of everything optional.

**The reason is a typed code, never free text.** Each label comes from the enumerated catalog —
`intervention_reason_label()` / `INTERVENTION_REASON_LABELS` (`cockpit/stopbanner.py`) — rendering the
code's short human label (e.g. `autopilot_no_candidates` → its label). The catalog is open by
construction: an unrecognized code passes through as its own text; an **empty code renders `"?"`** — the
banner never invents a message and never blanks. The full banner as reborn-specified carries three
bands — the `! STOP` reason line (yellow-bold), the `[ HUMAN — YOU HAVE CONTROL ]` keyboard-handoff
marker (the mode chip has flipped to the yellow Human register), and the `teach:` affordance line
(`A)nalyze  R)ecord` — Assign-Trigger unbound after calm `T` → Trade Loop). Red is *not* used here — red is reserved for hard link-down (the
viewport's own border reddens on disconnect); an autopilot halt is a **warning**, a screen it hasn't
been taught yet, not a failure, so it wears yellow.

## The confirm-gate dialog look

Arming a live run is the one money-path moment, and it is styled to look like one. In the Trade-Loop
library modal, selecting a chain **arms** a pending action and raises a single confirm line
(tip chain / arm surfaces under `cockpit/`; archive `_draw_loops_library` in `spectate_app.py` is
port-source):

```
Play "Ferren-Sol" x3 LIVE? y/N        ← danger-tone + reverse-video; a bare Enter does NOT fire
```

The line is drawn **`danger`-tone (red/bold) AND reverse-video** (`_tone_attr("danger", …) |
A_REVERSE`) — the only place the interaction contract combines the loudest tone with the selection
attr, precisely because it is the only place one keystroke could commit live turns. The prompt spells
out *what* runs and *how many cycles* (`x3`), the `y/N` capitalization signals the safe default is No,
and **Enter alone must never fire** — only a deliberate `y` commits. This is the −75/−78-turn-scar
doctrine made visible: the redder-and-reversed styling is the surface saying *this one spends real
money.* The same warn+reverse treatment marks the idle-prompt "Send…" line (tip play-shell draw;
archive `spectate_app.py` port-source), the lighter sibling of the same "this input goes live" cue.

## Liveness & motion on the strip

The mode line is a "is it frozen?" surface, so it carries live cues even when nothing is being sent:

- **The `→ TX` readout** flips between `→ 158` and `→ -` on every dispatch — the app's heartbeat of
  *keys actually pressed*.
- **The mode chip** flips color the instant Ctrl-A lands — immediate, unrefusable switch-to-Human shows as
  an instant green→yellow chip flip, no lag.
- **The classification pulse** (`_draw_header`, ~1.0s reverse) fires when the underlying screen class
  changes — the coarse "something just changed" signal that often precedes a halt.
- **The AUTO-LOOP progress bar** advances its `▸ cycle/total [███░░]` fill in the hint slot while a
  taught run plays — the "watch it replay" payoff.

All chrome animates decoupled from content (chrome at `ANIM_FPS=13`; the viewport redraws only on real
events), so the strip breathes without churning the game screen.

## Panel states — calm / alert / empty

- **Calm (App healthy)** — green chip, quiet cyan hint band, no intervention strip, `→ -` or a settling
  `→ N`. No color noise.
- **Alert (halt)** — the yellow-bold `!` strip appears above the status bar and claims height first; the
  chip has flipped to the yellow Human register; the wired teach moves (Analyze / Record) are offered on the banner.
- **Armed (confirm pending)** — the red+reverse `y/N` line is up; the surface is holding for a
  deliberate second keystroke and will not commit on Enter.
- **Empty / cold-join** — before a mode is known, the chip degrades sanely: an unrecognized/empty mode
  renders `mode.upper()` or `"?"` (`format_mode_badge`) rather than crashing or blanking; the hint band
  still shows. A read-only cold-join shows the muted **Spectate** chip — plainly "not a driver."

## Responsive fold

The control strip and its chip survive the cockpit fold ladder (`cockpit/layout.py::frame_layout`;
archive `spectate_layout.frame_layout` port-source).
In the **`minimal`** tier (≥82 inner cols) there is no side gutter, so the mode line rides the packed
header strip and the hint band abbreviates — but the tokens are chosen to fit **82 inner cols without
truncating** (tip bands are length-budgeted to that width; keep the same budget when extending). Height
degrades **header → control → ticker → viewport-border** in that order, but the
intervention strip's first-claim on leftover height means **a halt banner survives even as the control
strip is squeezed** — the escalation is the last thing to fold, never the first. The body never scrolls
horizontally: the hint band truncates from the right, it does not push the strip wider than the frame.
See the shared fold ladder in [visual-language](/surfaces/visual-language.md) `[ASPIRATIONAL]` /
[trainer-cockpit](/surfaces/trainer-cockpit.md) for the full threshold table.

## Glyph / status-marker vocabulary (this surface's slice)

- **`!`** — leads the STOP / intervention strip (the one-glyph "attention" mark).
- **`→`** — the sent-keystroke / TX channel (`→ 158`, `→ -`).
- **`▸`** — the armed/selected row marker in the chains library and the play-progress separator
  (`Playing <name> ▸ cycle/total`).
- **`?`** — an empty/unknown reason code in the banner, or an unknown mode in the chip.
- **`█` / `░`** (`#` / `.` ASCII) — the AUTO-LOOP cycle-progress bar fill.
- **`KEY)verb`** — the uniform hotkey-token shape on the hint band (`^A)ode`, `A)nalyze`, …).

The full cross-surface marker set (`✓ · ? ⊘ ★ ✦ ○ —` and the liveness glyphs) is the shared dictionary
— see [visual-language](/surfaces/visual-language.md) `[ASPIRATIONAL]`; the markers above are the ones
this surface actually renders.

## Feel

**Calm until it needs you, then unmissable.** The interaction contract is quiet at steady state — one
green chip, a low-key `→` telemetry channel, a cyan hint band that reads as chrome — and it stays out of
the way while the taught app covers the known. The instant autopilot meets an unknown screen the register
flips hard: a bold-yellow `!` banner that claims height ahead of everything optional, the chip snapping to
the yellow Human register, and the wired teach moves (Analyze / Record) placed exactly where the halt happened. And the single
place one keystroke could spend real money — the launch confirm — is dressed in the loudest tone the
palette owns (red + reverse), because the surface would rather look alarming than let an unguarded Enter
burn a turn. Terminal-native, semantic-monochrome-plus, honest: it names the actor, shows the keys it
presses, and never invents a reason it doesn't have.

# Code divergence

- **Space pause + G relaunch canonized (WO-CANON-DRAFT-AUTOLOOP-RELAUNCH-ZERO-COVERAGE).** Tip keys and
  wire semantics (`replays_from_start`, `sends_already_issued` honest-`?`) are documented under
  N5 Pause & relaunch above — closes the prior "no canon citation pins this key" gap in
  `cockpit/autoloop_controls.py`.

The reborn contract above is the target; the current code still carries pre-reborn framing in places
(DOCS WIN — recorded, not silently reconciled):

- **Archive mode badges are a four-way set that frames the app as AI.** Archived
  `spectate_layout._MODE_BADGES` maps `ai_pilot → "AI-PILOT"`, `auto_loop → "AUTO-LOOP"`,
  `human → "MANUAL — YOU HAVE CONTROL"`, `spectate → "SPECTATE"`. Tip play shell (PWO-060 ·
  `2ca3154`) ships the reborn **App/Human dual** (`APP` XOR MANUAL) with an AST vocabulary gate —
  archive AI-PILOT remains port-source only.
- **Mode toggles App↔Human on tip via Ctrl-A.** `MODE_KEY` (WO-P5-061-ENTRY / ADR-002) attaches from
  App/Spectate and returns to App-hold while Human-attached. Attached bare `M` = Move. Archive
  `spectate_app._handle_key` cycles `ai_pilot ↔ spectate` — port-source only. Prior "does not yet
  fully toggle" / migrate-off-`M` hedges retired (WO-FIX-ADR-002-COMPLETION-CLAIM-VS-UNCLOSED-SEAM).
- **`A` / `R` teach moves are wired on tip; calm `T` is Trade Loop.** Queue claim
  "A launches tw attach; R/T absent" was stale archive framing. Tip:
  printable `A`/`a` → Analyze overlay (WO-P5-069); `R`/`r` → Record (WO-P5-067);
  Mode attach is **Ctrl-A** (`MODE_KEY`), not printable `A`. Calm `T`/`t` →
  Trade Loop (`trade_loop_toggle`, WO-EXPLORE-TRADE-MODE-SPLIT).
  **Residual closed (WO-BUILD-ASSIGN-TRIGGER-REKEY · hub 2026-08-06):** Assign-Trigger
  module + `app.py` handler remain for non-calm / programmatic callers, but **no calm key**
  emits `assign_trigger` — Max's explore/trade-loop ruling retired it from the calm band
  (not remapped). STOP banner teach line stays `A)nalyze  R)ecord` only. Do not silently
  claim Assign-Trigger is calm-`T`, and do not invent a replacement calm letter without a
  fresh Max ruling.
- **The auto meter "AI" count — tip closed.** Archive
  `spectate_layout.format_autonomy_counts` rendered `App / AI · Hum`. Tip
  meter is `cockpit/covermeter.py` App-vs-Human only (`COV`; no live AI slice) —
  see [coverage-metrics](/engine/coverage-metrics.md) tip-stamp.
- **App chip wire-reachability.** Composer + `play.attached` plumbing are LIVE (060); App→Human via
  Mode is proven (061 kernel). Human→App entry = **Ctrl-A** (Batch 1b Ruled; CC `WO-P5-061-ENTRY`).
  Chip text **`APP`**. Ctrl-] from App-hold = **Ruled no-op stay App** (Batch 2/3). Spectate≠Mode.
- **Ctrl-A Mode · multiplexer prefix (operator note).** Max Batch 1b Mode chord is Ctrl-A. GNU
  `screen` (default) / often-rebinding `tmux` eat Ctrl-A before the trainer sees it — Mode looks
  dead with no on-screen error. Escape the mux (`Ctrl-A a` in screen) or rebind; do not invent a
  second Mode key. See findings Ruled stamp.
- **`L)chains` has two distinct populations (ADR-003).** Recorded macros
  remain the ordinary taught rows. `detected`-tagged discovered chains remain
  outside that store but are cursor-selectable for an exact semantic
  approve-scaffold. Enter only raises the visible default-deny gate; `y`
  confirms one fingerprint, one route, one pass, and the displayed cash/turn
  floors. Partial/truncated discovery cannot arm, and no current-best
  substitution is allowed. Panic halts either runtime. Tip display of the
  discovered section is `tw2002_aiclient/chain_search_view.py` — partial
  listings must wear a `PARTIAL_*` banner; truncated-empty ≠ "no chains"
  (see ADR-003 Consequences · `AUDIT-CANON-DRAFT-CHAINSEARCH-HONESTY-CONTRACT`).

# Citations

- [control-and-escalation](/architecture/control-and-escalation.md) — owns the control state machine,
  the App↔Human/switch mechanics, and the escalation reason-code catalog this surface renders from
  (defer, do not restate).
- [rule-macro-engine](/architecture/rule-macro-engine.md) — the `when(screen_match + guards) → do(macro)`
  data model the A/R/T keys assemble.
- [app-autopilot-model](/architecture/app-autopilot-model.md) — what run/panic arm and halt.
- `tw2002_aiclient/cockpit/autoloop_controls.py` — Space pause + G relaunch offer / confirm label.
- `tw2002_aiclient/cockpit/cycle_progress.py` — AUTO-LOOP cycle/total progress composer for the Play hint band.
- `tw2002_aiclient/session/protocol.py::_dispatch_autoloop_relaunch` — wire disclosure contract.
- [ai-teacher](/engine/ai-teacher.md) — the retrospective, on-demand teacher `A`/Analyze invokes.
- [macros](/engine/macros.md) — the taught keystroke capture `R`/Record produces.
- [coverage-metrics](/engine/coverage-metrics.md) — the App-vs-Human live-share meter and the
  separate teach-provenance axis.
- [trace-ledger](/engine/trace-ledger.md) — the `{app,human}` two-sender attribution the dual mode
  line reflects.
- [trainer-cockpit](/surfaces/trainer-cockpit.md) — renders this cluster and mode line in the frame.
- [spectate-and-attach](/surfaces/spectate-and-attach.md) — the read-only viewer (no lock) versus the
  live keyboard seat (`tw attach`, crash-safe lock release).
- Tip calm-band / teach tokens — `cockpit/teachband.py`, `cockpit/autonomy_keys.py`,
  `cockpit/reflex_controls.py` (`REFLEX_TOKEN`), `cockpit/chains.py` (`CHAINS_TOKEN`) — see
  **Tip token SSOT** above (`AUDIT-CANON-DRAFT-TEACH-BAND-CROSSREF`).
- Code modules grounded against — tip: `cockpit/control_seat.py` (dual chips / strip segments),
  `cockpit/tones.py`, `cockpit/stopbanner.py`, `cockpit/teachband.py`, `cockpit/layout.py`,
  `screens.py`, `session/control_lock.py`. Archive port-source: `spectate_app.py` (`_handle_key`,
  control strip draw), `spectate_layout.py` (`_MODE_BADGES`, `format_mode_badge`,
  `compose_control_strip`, `format_autonomy_counts`, `compose_intervention_strip`),
  `interactive_app.py` (`tw attach` seat).
