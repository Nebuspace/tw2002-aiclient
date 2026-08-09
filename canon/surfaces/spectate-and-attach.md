---
type: System
title: Spectate (Read-Only) & Attach (Interactive) Surfaces
description: The two dedicated human-facing surfaces on the one daemon — Spectate watches without ever touching the game, and Attach takes the keyboard live under a crash-safe single-writer lock.
tags: [surfaces, spectate, attach, watch-stream, control-lock, human-in-the-loop]
timestamp: 2026-07-24T22:57:00Z
---

The daemon owns exactly **one** telnet connection to the game, and the AI-native design drives it
through the one-shot `tw` verbs — but two surfaces exist specifically for a **human** to sit in
front of that one connection: **Spectate** (watch it, touch nothing) and **Attach** (take the
keyboard and fly). Both attach onto the *same* already-running daemon over its unix socket; neither
spawns or replaces it. They sit at opposite ends of the control model: Spectate never enters the
control rotation at all, while Attach is the human's live driving seat. This concept specifies both
surfaces and the settle-edge push-stream substrate they share; it does not specify the control-lock
state machine itself (see [Control & Escalation](/architecture/control-and-escalation.md)) or the
daemon/CLI split beneath them (see [the Session Engine](/architecture/session-engine.md)).

# Implementation status (tip `bba53d4` · Phase 4 CLOSED)

| Surface | Tip reality |
|---|---|
| WatchHub + daemon `subscribe` | **LIVE** (`tw2002_aiclient/session/watch.py`) |
| `tw watch` (ops CLI settle-edge tail) | **LIVE** |
| `tw attach` (thin control-lock attach) | **LIVE** — no full curses paint yet |
| `tw spectate` (ops curses HUD) | **RETIRED / WONTBUILD** — Max `@ 13:13:55Z`; spectate folded into cockpit (PWO-055 LIVE). Do **not** invent ops `tw spectate` |
| Product play-shell watch subscribe | **LIVE** (PWO-050 · `watchfeed.py`) — settle-edge consumed for GAME paint (PWO-052/053) |
| Product play-shell GAME viewport | **LIVE** glyph + per-cell color paint 80×25 (PWO-052 · PWO-053); disconnect chrome **LIVE** (PWO-054) |
| Product in-cockpit spectate state | **LIVE** (PWO-055) — `spectating` + muted `SPECTATE` chip + no-send tripwire |
| Product cockpit attach (Mode) | **LIVE** (PWO-056 · tip `2c2decc` · WO-P5-061-ENTRY) — Human lock + chip → `MANUAL — YOU HAVE CONTROL`; Mode chord = **Ctrl-A** (ADR-002; tip `MODE_KEY`, not printable `M`) |
| Product cockpit detach (Ctrl-]) | **LIVE** (PWO-057 · tip `bba53d4`) — lock released · SPECTATE restored · Esc≠detach |

Target contracts below remain prescriptive for ops F2 / Phase-5 surfaces not yet on tip.

# Spectate — the read-only observation surface

`tw spectate` is a standalone curses dashboard that **subscribes** to the daemon's watch-stream and
renders it, live, without ever entering the control rotation. It connects to an already-running
daemon over the unix socket, opens a dedicated `subscribe` stream, and reads settle-edge events off
it on a background thread feeding a queue — so the curses loop stays responsive to resize/Ctrl-C and
never blocks on the network. Because it is a separate process reading a broadcast stream, it can run
in its own terminal alongside whatever is driving the game.

**It holds no control lock.** In the control-mode state machine, `tw spectate` stays entirely out of
the rotation — it never calls `take_human()`, never reserves the driver slot, and cannot be handed
the keyboard. On the read stream it is strictly a reader: it never sends anything on the subscribe
connection, and nothing it does reaches `session.send()` / `session.send_raw()` — no byte it
produces ever hits the game wire.

**Multiple spectators are safe (N1).** The watch-stream hub keeps a *set* of subscriber queues and
broadcasts every settle-edge to all of them; any number of `tw spectate` clients (plus a live
`tw attach`'s own read half) can watch the same session at once without contending, because none of
them drives.

The dashboard composes several panes over the streamed screen: the **GAME** viewport (the live
cropped game screen in color), a parsed-state **HUD** sidebar (credits / sector / turns / cargo /
profit plus world metrics), an event **LOG** ticker (newest settle-edges), a menu-map / priorities /
port panel column, and a status/mode strip. The layout logic is pure and lives in
`spectate_layout.py`, kept testable and separate from the curses I/O in `spectate_app.py`.

## Reborn framing of watched actors

Everything the dashboard attributes to an actor uses the reborn live-sender set **`{app, human}`
only**. The HUD, the LOG ticker, and the coverage strip read the trace ledger's per-keystroke actor
tag, and there is no live "AI" sender to attribute anything to — the AI is a retrospective rule
*author*, never a live driver (see [Control & Escalation](/architecture/control-and-escalation.md)).
Any "AI" figure a surface shows is a distinct **teaching-provenance** axis (rules authored /
approved), never a live-drive share; the live coverage meter is **App-vs-Human** only, with live AI
share ≡ 0 (see [Coverage Metrics](/engine/coverage-metrics.md)).

# Attach — the interactive driving surface

`tw attach` is the human's live driving seat: a full-screen curses console that forwards the
operator's keystrokes, one at a time and unbuffered, straight to the daemon's single game connection,
with the live screen streaming back in real color. TradeWars reads most menu commands a single
keystroke at a time, so keystrokes go out raw and immediately — no local line-editing or batching.

It opens **two** connections before curses ever touches the terminal:

- a **read half** — the same read-only `subscribe` stream Spectate uses, reused wholesale; and
- a **write half** — a persistent `attach` connection dedicated to forwarding keystrokes.

**Attach takes the control lock; Spectate never does.** Opening the write connection is exactly the
moment the daemon takes the human control-lock (`take_human()`); the human wins the keyboard
**immediately and unconditionally** — never blocked, never refused merely because an autopilot
dispatch is mid-flight (that in-flight dispatch is *fenced* and the human's first keystroke is held
off the wire only until the fenced dispatch cleanly releases, so the one wire is never interleaved by
two writers). An attach is rejected only when the keyboard is already exclusively held — another live
attach (`already_attached`) or a running background loop (`locked_by_auto_loop`) — in which case the
rejection is reported in plain text before curses ever takes over the terminal.

**Crash-safe lock release on every exit path (C6 — the single-writer guard).** The lock is held for
exactly as long as the write connection stays open, and released on **any** way out — clean detach,
Ctrl-C, or a dropped/crashed socket — because the daemon takes the lock and then does everything
else inside a `try/finally` whose `finally` always calls `release_human()`. A crashed or killed
attach session therefore can never wedge the daemon in human-controlled state. On the client side,
both the buffered file wrapper and the raw socket are closed on exit so the daemon's `readline()`
reliably sees EOF and the release actually fires. Every forwarded keystroke is also recorded to the
trace ledger with `actor="human"`, so attach play is attributed correctly in coverage and retro.

The detach key is **Ctrl-]** (ASCII 29, the classic telnet escape) — deliberately *not* `q` or
Ctrl-C, because those are live TradeWars menu commands (`Q` quits the game) and reusing them would
eat real game input.

# The watch-stream substrate (N2)

Both surfaces are fed by one settle-edge **push-stream** engine (`WatchHub` in `watch.py`). A small
background thread watches the session's already-rendered screen and detects **settle edges**: moments
where the screen has both (a) stopped changing (idle ≥ a debounce window, default ~350 ms —
*hypothesis: the default debounce is a tuned constant, not a game fact*) and (b) actually changed
since the last edge it announced. Each edge is broadcast, as a protocol-response-shaped event, to
every currently-subscribed queue. A newly subscribing client is seeded with the current settled
screen as its first event, so a spectator tuning in mid-session sees state immediately rather than a
blank pane until the next change.

This is deliberately **separate** from the synchronous settle detection that answers "has *this
send* settled yet" for a single `do`/`read` call (see
[Settle Detection](/architecture/settle-detection.md)): the watch-stream instead answers "what is the
game doing right now," continuously, for however many passive spectators are attached. Both read the
same session state under the same lock; they do not interact. The hub also carries a side channel for
events that are not screen-changes at all (e.g. a background loop's per-cycle progress), stamped the
same way so a consumer cannot tell the two apart by shape. Nuisance auto-handling (auto-dismissing
repeated pauses, etc.) is explicitly *not* this engine's job — it streams every settle-edge as-is.
This section is the **surface contract** the two dashboards rely on, not the transport's internals.

# Color rendering (N3)

The GAME viewport preserves the game's own per-cell color. `pyte` tracks each cell's foreground /
background / bold; the daemon serializes those as color runs, and the curses renderers paint each run
with its own attribute (mapping pyte's basic-8 color names to curses colors, degrading gracefully to
plain bold/normal when the terminal lacks color or exhausts its color pairs). The game's native
conventions therefore carry through visually — *hypothesis: red marks hostiles and cyan marks menu
chrome in the stock TradeWars palette*, rendered as the server sends them, not reinterpreted by the
client. Separately, the dashboard's own chrome applies a small **semantic** tint set to *parsed*
state — green = ok/gain, yellow = warn, red = danger/loss, cyan = info — which is authored UI
signalling layered over the raw screen, distinct from the game's own cell colors.

# Visual design & polish

This section specifies the *look* of the two surfaces across the nine polish dimensions. The
color-semantics table, the glyph/marker set, the border-weight hierarchy, the liveness-cue catalog,
and the fold ladder are **shared vocabulary** consumed identically by Spectate, Attach, and the
[Trainer Cockpit](/surfaces/trainer-cockpit.md) — they are literally the same
`spectate_layout.py` / `terminal.py` code paths rendering all three. The canonical dictionary of
that vocabulary lives in [Visual Language](/surfaces/visual-language.md) *(forward-reference — a
recommended-but-not-yet-created 37th concept; until it exists, the grounded tables in the UI-polish
assessment are the source of truth)*. What follows is the **surface-specific application** of that
vocabulary to Spectate and Attach — the sentences, not the dictionary.

## Color semantics on these surfaces

Two color systems coexist on-screen and must never be confused (this is the same distinction the
[Color rendering](#color-rendering-n3) section draws, restated as a design rule):

- **Game-native per-cell color** fills the GAME viewport. `terminal.color_map()`
  (`terminal.py:65-94`) RLE-encodes pyte's SGR fg/bg/bold per row; `_ColorPairs`
  (`spectate_app.py:527`) lazily allocates one curses pair per distinct `(fg,bg)`, degrading to
  plain bold/normal when the terminal runs out of color or pairs. This is the server's true CP437
  color, reproduced, never reinterpreted. *Hypothesis (kept deliberately un-promoted): the stock
  TradeWars palette uses red for hostiles and cyan for menu chrome — rendered as the server sends
  it, unverified by us, and must stay hypothesis-marked wherever a surface repeats it.*
- **Dashboard semantic tint** colors *parsed* state in the chrome. One 7-tone table
  (`_SEMANTIC_COLORS`, `spectate_app.py:1098-1114`) drives every surface, so a tone always means the
  same thing: `ok` green-bold (profit/healthy), `warn` yellow-bold (stale/attention), `danger`
  red-bold (hostile/disconnected/loss), `info` cyan non-bold (menus/neutral/selling), `gain`/`loss`
  the green/red credit-delta flashes, `muted` genuinely-uncolored (parked). pyte names ANSI-yellow
  `"brown"`; it renders yellow. The load-bearing rules: **cyan is chrome, never data**, and
  **reverse-video (`A_REVERSE`) is the single selection/active/badge signal** across the whole UI.

**Spectator sidebar & ticker tinting.** The parsed-state HUD sidebar reads each metric through the
shared tone set — a healthy turns-gauge is `ok` green, a stale-rx status cell goes `warn` yellow via
`status_semantic(connected, age)` (`spectate_layout.py:2681`, `warn` at `last_rx_age_s ≥ 5.0s`), a
credit drop flashes `loss` red. The event LOG ticker's newest row flashes bold on arrival
(`TICKER_FLASH_DURATION_S=1.0`) then settles — the settle-edge the watch-stream delivered made
visible as motion.

**Attach borrows only the game colors.** `tw attach` is full-screen game (no sidebar to tint), so on
it the game-native per-cell color is essentially the *only* color — the sole chrome element, the
status bar, is drawn in reverse-video rather than a semantic tone (see Panel states below).

## Box-drawing, borders & titles

Both surfaces inherit the **two-weight border hierarchy** (`cockpit/draw.py` `DOUBLE_*` /
`THIN_*`): the live game viewport wears a **double-line** box (`╔ ╗ ╚ ╝ ═ ║`, ASCII `+ = |`) while
all instrument chrome wears **thin-rounded** boxes (`╭ ╮ ╰ ╯ ─ │`, ASCII `+ - |`). The heavier
double-line deliberately gives the CP437 world visual primacy — a BBS/DOS-door echo — so the eye
lands on the game first and reads the HUD as its frame. See
[Visual Language](/surfaces/visual-language.md) for the full table.

- **Spectate** composes titled thin-rounded boxes for its instruments (`HUD`, `LOG`, `MENU MAP`, and
  the priorities/port column), each title drawn at `addnstr(0, 2, " TITLE ")` in cyan, all wrapped in
  the single double-line outer frame (`_draw_outer_frame`, cyan bold) that makes the whole client
  read as one cockpit. The GAME viewport is a double-line box titled `" GAME "` with **zero inner
  padding** — border on row/col 0, content at (1,1) — because any inset would shear the game's own
  CP437 box-art (`_content_inset`).
- **Attach** is intentionally frame-*lean*: it is a single full-screen MAIN pane giving *every* column
  to the authentic game screen, with no sidebar/ticker split (`_render`, `interactive_app.py:239-244`).
  Its only chrome is the one-row status bar.

## Spacing, alignment & crop geometry

The GAME viewport content area is **always ≤ the native 80×25 grid, centered, never stretched** to
fill leftover space — `game_w = min(GAME_W, viewport_w - 2)` / `game_h = min(GAME_H, viewport_h - 2)`
(`spectate_layout.py:505-506`); it is only *clipped* when a fold tier genuinely lacks room for the
full native size. Because the daemon already crops the screen, `cropped(0,0) == native(0,0)` — the
top-left game cell maps to the top-left viewport cell with no offset, which is what lets the
zero-inset double-line border sit flush against real game content. On Spectate the sidebar sits in
fixed-width gutters flanking that centered viewport; on Attach the game pane simply fills the whole
terminal minus the status row (`body_h = max(1, lines - 1)`, `interactive_app.py:245`).

## Panel states

- **Stale / blurred:** a persistent value that has gone stale dims to `A_DIM` past the freshness
  threshold (20s) — the same "honest liveness" rule the whole client obeys; a spectator sees a HUD
  cell fade rather than silently lie about being current.
- **Attach's active status bar:** the entire bottom row is drawn in reverse-video
  (`curses.A_REVERSE`, `interactive_app.py:250`) — a surface-specific fact: on the driving seat the
  status bar is *always* the active/attention chip, reading
  `ATTACHED -- Ctrl-] detach | sent:{n} → {last}` (`_STATUS_TEMPLATE`, `interactive_app.py:161`).
  Reverse-video here is the same "this is live/active" signal reverse-video carries everywhere else,
  applied to the one bar that says the human currently holds the keyboard.
- **Link-down on the frame itself:** the viewport border flips cyan → **red non-bold** when not
  connected (`spectate_app.py:2258`) — an unmissable "link down" cue on the frame, never touching game
  content. On disconnect the viewport shows a calm placeholder set (`WAITING_SESSION_LINES`), *not* a
  frozen stale login prompt, while the client reconnects on bounded backoff.
- **Empty / cold-join:** a newly-subscribing spectator is seeded with the current settled screen as
  its first event (see [the watch-stream substrate](#the-watch-stream-substrate-n2)), so it paints
  real state immediately instead of a blank pane until the next change — the cold-join is warm by
  construction.

## Liveness & motion

The watch-stream substrate above is the *data* engine; these are the *visual* cues it drives — the
cues that kill "is it frozen?". Each Spectate settle-edge event surfaces as: the **LOG ticker flash**
(newest row bold ~1.0s), a **freshness stamp** (`✦ Ns ago` / `✦ now`, dimming past 20s) on every
persistent value, a **credit sparkline** + **delta chip** (`▲`/`▼`) tween when credits move, a
**turns fuel-gauge** (`[███░░░]`, green→amber→red by `gauge_semantic`), an always-breathing
**heartbeat** (`●`/`○`) and a **waiting spinner** (braille ramp, frozen at rest). Chrome animates at
a steady low frame-rate decoupled from content so the dashboard never flickers and never looks dead.
See the full catalog in [Visual Language](/surfaces/visual-language.md).

On **Attach**, liveness is more literal: the visible **caret tracks the game's own cursor position**
(`main_win.move(cy, cx)`, `interactive_app.py:258-263`) the way a real BBS terminal would, and the
status bar's `sent:{n} → {last}` **TX readout** echoes each forwarded keystroke — the "-> 158"
sent-keystroke channel — so the operator sees their own input register even when the game is briefly
silent.

## Responsive fold

Spectate degrades through the shared **fold ladder** (`frame_layout`, `spectate_layout.py:237`):
full two-gutter layout → single-gutter → HUD-on-header `minimal` → border-dropped `no_border` →
`too_small` refusal, keyed on inner content-column budget. The **body never scrolls horizontally** —
the viewport is fixed ≤80 wide and the LOG truncates to its line-tail rather than overflowing. This
graceful *layout* fold is distinct from the *event-loop* resize responsiveness both surfaces already
have (the background reader thread keeps the curses loop answering SIGWINCH/Ctrl-C without blocking on
the network). Attach, being a single full-screen pane, simply re-flows the game pane to the new size
on resize; it has no multi-panel fold to perform.

## Glyph & status-marker vocabulary

Both surfaces draw from the shared marker set, which ships as **Unicode/ASCII twin tables** switched
by one `unicode_ok` flag — an 80-col non-UTF-8 terminal loses fidelity, never information. The marks
a spectator sees most: `✦` freshness, `→` sent-key/step arrow, `⇒` LOG "landing differs" suffix, `★`
you-are-here / current-sector highlight, `—` (em-dash) for an unknown/empty value, and the mode-badge
chips (`AUTO-LOOP` ok/green · `MANUAL — YOU HAVE CONTROL` warn/yellow · `SPECTATE` muted/plain · the
AI-teach badge info/cyan, a **teach-overlay** indicator, never a live-drive mode). The full meaning
and styling of the marker set — including the priority markers `✓ · ? ⊘` and the yellow-bold
**intervention `!` strip** that height-claims itself above everything optional on `needs_attention` —
is catalogued in [Visual Language](/surfaces/visual-language.md).

## Feel

Both surfaces aim at the same north star: **dense-but-readable, terminal-native, calm-until-it-needs-you.**
Spectate is a quiet instrument wall that lets you watch a trainee learn — game-native color front and
center, cyan chrome framing it, honest freshness stamps on everything, no color noise until something
actually needs you, at which point a bold escalation muscles to the top. Attach strips even that away:
one authentic full-screen game, one reverse-video bar that says *you have the keyboard*, a caret that
follows the game's own cursor — a real BBS terminal with a single honest line of chrome. Both degrade
with dignity (Unicode/ASCII twins, column-budget fold, never a sideways-scrolling body) and both are
hand-built on pure stdlib `curses` with zero added packages.

# Schema

| | Spectate (`tw spectate`) | Attach (`tw attach`) |
|---|---|---|
| Purpose | read-only observation dashboard | live interactive driving seat |
| Connections | one `subscribe` read stream | `subscribe` read stream **+** persistent `attach` write connection |
| Control lock | never taken — outside the rotation | taken on connect (`take_human`), released on every exit (`release_human`) |
| Emits game keystrokes? | No | Yes — the human's own input, one keystroke at a time |
| Concurrency | many spectators safe (N1, broadcast set) | exclusive — one attach at a time; rejects if already-attached / loop-locked |
| Detach / exit | `q` / Ctrl-C | Ctrl-] (never `q`/Ctrl-C — those are game commands) |
| Ledger actor | n/a (sends nothing) | `human` (each keystroke recorded) |

# Examples

```
Spectating a live session:
1. A daemon is already running and connected (`tw status` confirms it).
2. In a second terminal: `tw spectate`. It opens a subscribe stream and paints the
   GAME/HUD/LOG dashboard, seeded immediately with the current settled screen.
3. Whatever is driving the game keeps driving; the spectator only watches. Any number
   of additional `tw spectate` clients can attach at once — none of them touches the wire.
```

```
Taking the keyboard, then handing it back:
1. `tw attach` opens both connections. The write connection takes the human control-lock;
   the keyboard is the human's immediately (any in-flight autopilot dispatch is fenced,
   not raced onto the wire).
2. The human types; each keystroke is forwarded raw and recorded to the ledger as `human`.
   The live screen streams back in color over the read half.
3. The human hits Ctrl-] to detach. The write connection closes, the daemon's `finally`
   releases the lock, and control returns to App — even if the terminal had crashed instead.
```

# Code Divergence

**`spectate_app.py` / `tw spectate` — tip closed (deleted / RETIRED).** The dual-hatted archive
binary (read-only viewer + Trainer Control Panel META-commands `set_mode` /
`play_start`/`play_stop`/`play_pause`/`play_resume`) was removed by the rebirth scaffold
(`452d896`). Tip observation is **in-cockpit Spectate** ([Trainer Cockpit](/surfaces/trainer-cockpit.md)
· PWO-055) plus daemon-free `tw watch` settle-edge streaming. Control-plane mode / autoloop arming
lives on the cockpit mode-line / wire `autoloop_*` verbs — not a separate spectate binary.
`tw spectate` remains **RETIRED / WONTBUILD** (Max); see [CLI Verbs](/architecture/cli-verbs.md).

**The word "spectate" names two different things.** In-cockpit Spectate / `tw watch` (observation)
stays *outside* the control-mode state machine as a game-wire reader. There is *also* a
`MODE_SPECTATE` control-lock state meaning "driving paused, nobody is driving" — the panel's
explicit pause / panic-landing mode. They are unrelated: the viewer never enters that mode, and
that mode is not the viewer. Recorded to prevent conflating the observation surface with the pause
state.

**Coverage meter naming.** Under the reborn model the only live coverage meter is **App-vs-Human**
share (live AI share ≡ 0). Archive `spectate_layout.py`'s `autonomy_ratio` gauge is gone with the
binary; the meter's reborn definition lives in [Coverage Metrics](/engine/coverage-metrics.md).

**`MODE_AI_PILOT` — retired on tip (2026-08-04).** Attach's `take_human()` still fences an
in-flight App dispatch / auto_loop hold (not an `ai_pilot` mode string — that drive mode is gone
from tip `tw2002_aiclient/session/control_lock.py`). The AI never sends a live keystroke; live
senders remain `{app, human}` only. Resolution recorded in
[Control & Escalation](/architecture/control-and-escalation.md)
(`AUDIT-CANON-DRAFT-AI-PILOT-RETIREMENT-STALE`).

# Citations

[1] Archive `twclient/spectate_app.py` / `spectate_layout.py` — deleted by rebirth; historical dual-hat viewer + META-command panel (do not cite as tip)
[2] `tw2002_aiclient/cockpit/` + in-cockpit Spectate (PWO-055) — live observation surface
[3] `tw2002_aiclient/session/attach_client.py` + `tw attach` (`session/cli.py`) — interactive keyboard; Ctrl-] detach
[4] `tw2002_aiclient/session/watch.py` (WatchHub settle-edge push-stream; `tw watch`)
[5] `tw2002_aiclient/session/control_lock.py` (tip control-mode state machine; take_human/release_human; MODE_SPECTATE pause state; `{app, human, spectate}` only)
[6] `tw2002_aiclient/session/daemon.py` / protocol attach path — take_human on connect, try/finally release_human on every exit path
[7] canon/architecture/control-and-escalation.md (the control dual, {app,human} attribution; MODE_AI_PILOT retirement DONE)
[8] twclient/terminal.py (color_map RLE per-cell SGR encode — game bytes only; chrome borders live in cockpit/draw.py on tip)
[9] twclient/spectate_app.py (_SEMANTIC_COLORS 7-tone table; _ColorPairs lazy allocation; viewport red-on-disconnect border)
[10] .samantha/plans/ui-polish-assessment.md (shared visual vocabulary — grounded color/glyph/border/fold tables; forward-ref for /surfaces/visual-language.md)
