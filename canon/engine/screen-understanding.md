---
type: System
title: Screen Understanding — Classification & Best-Effort State Extraction
description: The deterministic semantic read that turns one settled rendered screen into a screen class plus a best-effort structured game state, feeding rule screen-matching, the world model, and the HUD — and, by producing "unknown", the literal trigger that stops the autopilot and hands the keyboard to the human.
tags: [engine, classification, state-extraction, stop-on-unknown, best-effort, stale-scrollback, menu-signature]
timestamp: 2026-07-23T19:47:47Z
---

Screen understanding is the layer that turns one **settled** rendered screen into two things:
a **screen class** (what kind of screen this is) and a **best-effort structured game state**
(credits, sector, turns, port, warps, cargo — whatever the screen legibly encodes). It is a
pure, deterministic read: regex anchors over rendered text, no AI reasoning, no live keystroke,
no memory of its own. It never drives — it only *describes*. Three consumers read what it
produces: the [Rule–Macro Engine](/architecture/rule-macro-engine.md) matches the screen class
against taught rules, the [World Model](/engine/world-model.md) ingests the structured state,
and the trainer HUD displays it.

In the reborn contract this passive read carries a load-bearing role. The single most important
value it produces is `unknown`: a screen class of `unknown` is the **literal trigger** for
stop-on-unknown. When classification returns a recognized class, a taught rule *may* fire
(the reflex layer decides); when it returns `unknown`, the autopilot stops and the keyboard goes
back to the human. Recognition here is therefore the boundary between "the app handles this" and
"the human must." Getting a *false* recognition wrong is worse than getting an unknown right —
so the whole design leans toward refusing to claim more than the screen actually says.

# The Two Outputs

- **`screen_class`** — a single label from a fixed vocabulary
  (`main_command`, `computer`, `port_trade`, `sector_display`, `menu`, the login/interstitial
  states `login_name` / `login_password` / `ansi_prompt` / `game_select` / `char_create`, the
  mid-flow gates `pause_key` / `warp_confirm` / `money_prompt`, content classes
  `stardock_cargo_hold_quote` / `stardock_shipyard_listing`, `cim_report`, and the catch-all
  `unknown`). **`money_prompt` is never-auto-action** (App escalates; no macro may fire) —
  Max carte blanche Accept 2026-07-26 in `DECISIONS.md`. StarDock quote/listing classes are
  content anchors with exclusivity/provenance discipline (same distrust-of-bare-shape family
  as `cim_report`).
- **`state`** — a partial dict of whatever structured fields the screen legibly encodes. Missing
  or unreadable fields are simply **omitted**, never guessed. Partial state is normal and fine.

Both are derived by `classify.py` and `state_parser.py` respectively, each a pure function of the
rendered text. Neither reads the game; neither writes anything; neither ever picks an action.

# Classification: Regex Anchors, Gate vs Content

Classification is a scan of the rendered text against ordered regex **anchors**. Anchors fall
into two structurally different kinds, and the distinction is a safety mechanism, not a stylistic
one:

- **Gate anchors** — a single, currently-active blocking request: `pause_key`, `login_password`,
  `login_name`, `ansi_prompt`, `game_select`, `char_create`, `computer`, `warp_confirm`,
  `main_command`, `money_prompt`. In real TWGS/TW2002 play the server is blocked waiting *right
  there*, so a gate is always the last thing printed. A gate anchor is therefore trusted only against the **current
  prompt line**, never the whole screen. A gate pattern found only deeper in the buffer is stale
  leftover text sitting in an unclaimed region of the pyte grid (pyte never clears cells the
  server did not overwrite), not a live gate. This was caught live: a rules screen's decorative
  `[Pause]` marker lingered above an already-active `Enter your choice:` menu prompt, and naive
  whole-screen scanning misread it as `pause_key`.
- **Content anchors** — describe what *kind* of screen this is and legitimately live a few lines
  above the prompt: `sector_display`, `port_trade`, `menu`, `stardock_cargo_hold_quote`,
  `stardock_shipyard_listing`. These are allowed to match anywhere in the full screen text.

Order matters and is deliberate. **Gate anchors are checked before content anchors.** Within the
gate list, more specific anchors precede their supersets: `computer` (`Computer command [TL=…]`)
is checked before `main_command` (`Command [TL=…]`) because the computer prompt is a superset of
the ship prompt and would otherwise be swallowed by it; `warp_confirm` (the mid-warp
`Do you really want to warp there? (Y/N)` gate) is checked before the `sector_display` content
anchor because the Sector body is still on screen above that prompt — without the gate winning,
the autopilot held forever on a real live stall.

`money_prompt` is checked **last among the gates**, so it can never take a screen from a class some
consumer drives; it still precedes every content anchor, so a finished quote block cannot give a
*live* money question a benign, teachable identity. That ordering is the whole safety argument: the
real captured `stardock_cargo_hold_quote` screen classifies as `money_prompt` while the server is
blocked on "how many holds would you like to buy", and reverts to its block identity only on the
no-prompt path where nothing is being asked.

The never-auto-action pin is enforced, not merely stated: `classify.NEVER_AUTO_ACTION_CLASSES` is a
frozenset that consumers **derive** their refusals from (`menu.crawler._NON_MENU_GATE_CLASSES`
unions it) rather than restating, and an import-time assertion rejects a name no anchor can ever
return — because a misspelled pin forbids nothing while every consumer stays green.

**Verification status:** the quantity shape (`how many … ?`) is VERIFIED against a live capture; the
bank-transfer shape is a HYPOTHESIS named by the ruling and not yet observed. `Your offer [N] ?` is
deliberately **not** claimed by `money_prompt` — [auto-haggle](/engine/auto-haggle.md) owns that
shape prescriptively, and claiming it here would silently overrule a different Accepted concept.

**That tension is now RULED** (`DECISIONS.md` §A.2, Max carte blanche 2026-07-26): never-auto-action
means **no unattended freestyle**, and **human-armed guarded rules are exempt** — auto-haggle and
taught quantity chains may answer their own shapes. So `Your offer [N] ?` must stay unclaimed by
`money_prompt`: the abstention above is the ruling's requirement, not a gap awaiting one. What
`money_prompt` forbids is an *unattended* answer to a money question the app was never taught.

The live entry point is `classify_screen(full_text, prompt_line)`: it evaluates gate anchors
against the **prompt line only**, content anchors against the whole screen, and gate anchors
against the whole screen *only* as a last resort when there is no prompt line at all. A legacy
whole-text `classify(rendered_text)` also exists for isolated strings (tests, one-off checks);
it is order-dependent and can produce a false gate match on stale grid content — see the Code
Divergences note.

Two multi-signal classes cannot be decided by a single-line anchor and are checked ahead of the
ordinary passes: `cim_report` (a genuine system-generated port report is trusted only when
**nothing else shares the screen** — an exclusivity check, since a help screen or a forged
transmission can reproduce the report's punctuation byte-for-byte) and the boxed / banner
variants of `game_select` (trusted only on a combination of the current prompt line plus
adjacent, exclusive, distinctive body content — hardened repeatedly against stale-scrollback and
forged-fragment attacks). The rule these share: **text-matching a screen's own shape is never a
sufficient trust signal**; provenance (exclusivity, adjacency to a genuine current prompt) is.

> **Case sensitivity, one subtlety worth stating.** Classification anchors are
> case-*insensitive* (`re.IGNORECASE`). The `wait_prompt` regexes consumed by settle detection
> are case-**sensitive** — a case-mismatched prompt regex silently times out rather than erroring.
> These are two different layers with two different disciplines; do not assume one from the other.
> Settle is upstream — see the Boundary section.

# The Unknown Is First-Class

`unknown` is not an error and not a gap to be minimized into oblivion — it is a designed output
with a specific downstream meaning: **stop the autopilot, escalate to the human.** Classification
returns `unknown` whenever no anchor matches, and that is exactly correct — the app has met a
screen it has not been taught to recognize, which is the moment the human is supposed to take
over (the escalate-on-unknown contract lives in
[Control & Escalation](/architecture/control-and-escalation.md)).

The same first-class posture governs state extraction. Every parser is **best-effort**: when a
field cannot be read with confidence, it is omitted, and the HUD renders the sticky last-known
value with a freshness mark or a bare `?` / `-`. The layer **never fabricates** a value to fill a
hole. A missing credits reading is `?`, not a zero; an unreadable sector is absent, not a guess.
This matters because guards and coaching read these fields — a fabricated value could silently
satisfy a guard that should have fired, or mislead the human. Unknown-degrade is the safe
default; invention is never allowed.

# Best-Effort State Extraction

`state_parser.parse_state()` extracts, as available: `sector`, `turns_left` (or a `turn_timer`
HH:MM:SS on servers that repurpose `TL=` as a countdown), `credits`, `warps` (the adjacency list
for the current sector), `port` (flyby presence and, when a docked commerce report is on screen,
per-commodity buy/sell status + amount + percentage), and `fighters_aboard`. Batch screens (a CIM
port report, a multi-sector scan) are ingested by `parse_port_report()` into many partial
per-sector records in one pass.

Every field obeys three disciplines:

1. **Anchor to the LAST match** (see the next section) — the hard invariant.
2. **Line-shape provenance, not keyword presence.** A genuine in-game status line is its own
   line (`Sector : N` at line start, `Warps to Sector(s) :` at line start); a chat or narrative
   mention embeds the same words mid-sentence. `_SECTOR_RE` is anchored to line start
   (`re.MULTILINE`) precisely so a same-screen chat line (`…Sector: 8675, come check it out!`)
   cannot be mistaken for the bot's real sector.
3. **Block-scoped, gated reads for anything persisted.** Commodity rows are extracted only from
   the contiguous block beneath the latest commerce-report anchor — the *same* block
   `is_genuine_port_report()` validates — so the gate and the written value always read the
   identical block. A world-model write is additionally provenance-gated:
   `is_genuine_sector_status()` (a `Sector : N` line followed, before the next blank line, by a
   sibling `Ports :` / `Warps to Sector(s) :` marker) and `is_genuine_port_report()` (a real,
   fully-shaped commodity row present) exist so that narrative text merely *reproducing* a
   status line's shape does not get ingested as real sector data.

A dedicated `sector_from_command_prompt()` reads the current sector off the settled screen's own
trailing `Command [TL=…]:[NNNN]` prompt, because a warp landing on a port streams
arrival → auto-dock → commerce report as one burst that can scroll the `Sector : N` line off the
fixed 80×25 viewport (pyte carries no scrollback) — the same-screen prompt anchor is present
exactly where a cross-screen anchor would have gone stale.

The exact numeric grammars here — the density-scan value table, the CIM row layout, per-server
`TL=` semantics — are **best-effort over live-captured shapes and are extended as live play
reveals more**. Where a grammar is constructed rather than live-verified, it is hypothesis-tagged;
see Verification status below.

# The Last-Match Invariant (Hard Rule — Never "Simplify")

Every extracted field anchors to the **LAST match in the buffer — the bottom-most, most recently
printed occurrence — not the first.** This is deliberate and load-bearing, and it must never be
"simplified" back to a naive first-match `re.search()`.

The reason is stale scrollback. pyte emulates a fixed 80×25 grid and never clears cells the
server did not overwrite, so an earlier, now-stale value can sit in the buffer *above* the
genuinely current one. First-match-wins reports the stale value. Both failure directions were
caught live: a lingering `We'll sell them for 132 credits.` offer sentence outranked the real
`You have 100,485 credits` balance and corrupted a reward delta by +90,661cr; a stale pre-warp
`Sector : 1234` outranked the post-warp `Sector : 5678`. Last-match wins fixes both. A screen can
even print `You have N credits` twice legitimately (pre-transaction context, then post-transaction
result) — last-match takes the real final balance.

The one refinement to naked last-match is provenance (see above): last-match makes a field
**forgery-resistant against an earlier forged line** but, by the same shape, vulnerable to a
*later* one. The current provenance gates are shape checks, not identity checks — a documented
residual family (a forged in-band line landing after the genuine one on the same settled screen)
is bounded today by solo-play (no other player exists to author such a line) and is tracked as a
single anchor-to-live-prompt / exclusivity hardening prerequisite before any autonomous run on a
multiplayer or shared server. That residual is a *limitation of the provenance layer*, never a
license to weaken the last-match rule itself.

# Menu-Screen Signatures

A stable **menu signature** — `menu_sig.menu_signature(full_text)`, a short SHA-256 over the
screen's identifying text with leading/trailing blank lines and trailing per-line whitespace
normalized away, so cosmetically-identical renders hash identically — is the shared primitive by
which a menu screen is *identified across visits*. It lives in its own pure module (importing only
`hashlib`) so its three consumers do not transitively pull in the daemon's live-connection deps
just to hash a screen: the menu **crawler** (the producer, persisting nodes as it discovers them),
menu **localize** ("you are here" lookup over the known menu graph), and the escalation-driven
map-extension work. Because the signature is computed identically everywhere, a menu the crawler
recorded, the navigator localizes to, and the human teaches against are all keyed the same way.
The menu graph these signatures node is owned by
[Menu Map & Introspection](/engine/menu-map-and-introspection.md); this concept owns only the
signature primitive that keys it.

# Boundary — Settle Is Upstream

Screen understanding operates only on a **settled** screen — one settle detection has already
declared stable. Settle is not this concept's job: deciding when a screen has stopped changing,
and honoring the case-sensitive `wait_prompt` regexes a caller supplies, belongs entirely to
[Settle Detection](/architecture/settle-detection.md). This layer consumes that settled render
and asks only "what is this, and what does it say." An unsettled or mid-arrival screen is not
classified — a half-printed report, for instance, is treated as not confidently closed and is not
parsed.

One further boundary worth stating: the secret-prompt predicate `is_probable_secret_prompt()`
lives in `classify.py` but is a *redaction* helper for the interactive attach keystroke path, not
a classification anchor. It is deliberately broader and fail-safe (it errs toward treating an
ambiguous keyword-bearing prompt as a secret) so password-shaped prompts redact TX. It is still
a *heuristic*: prompts with none of its keyword vocabulary can still log attach keystrokes in
cleartext (named residual — pinned by attach redaction tests). The narrow `login_password` gate
anchor stays narrow because it also drives the automated login automaton's decisions, not just
its logging. The redaction discipline itself (every secret send routes through `log_redacted()`;
no secret ever touches logs, argv, or the repo) is owned by
[Secrets & Credentials](/doctrine/secrets-and-credentials.md) — stated once, deferred here.

# Verification status

- **VERIFIED (live-captured):** the `main_command` / `computer` / `sector_display` / `port_trade`
  anchors; the `game_select` boxed and banner variants; the flyby `Ports :` line, the
  `Warps to Sector(s) :` paren-wrapped destination shape, and the docked commerce-report column
  layout — all grounded in captured fixtures and live traces.
- **HYPOTHESIS (constructed, not yet live-captured):** the CIM/batch `parse_port_report` row
  grammar (`-=-=- Port Report (CIM) -=-=-` header/footer, `Sector N  Class: XXX  F:N% O:N% E:N%
  Warps: n-n-n` rows) and the density-scan value table
  (`1=beacon · 5=fighter · 10=mine · 40=ship · 100=port/StarDock · 500=planet`). These are
  constructed from independently-verified TW2002 conventions plus this project's own real-capture
  shapes; expect a refinement pass once the daemon sees a real CIM/scan screen. Consumers must
  treat their output as provisional until a live capture confirms the grammar.

# Code divergence

This concept is control-neutral, and the read modules (`classify.py`, `state_parser.py`,
`terminal.py`, `menu_sig.py`) are broadly faithful to the reborn target — they are pure,
deterministic, never drive, and already treat `unknown` and missing fields as first-class. The
divergences worth recording are narrow:

- **Legacy whole-text `classify()` alongside the prompt-aware `classify_screen()`.** The reborn
  stop-on-unknown trigger must run on `classify_screen(full_text, prompt_line)`, which scopes gate
  anchors to the current prompt line and is resistant to stale unclaimed grid content. The older
  `classify(rendered_text)` scans the whole text with gate anchors and, by its own docstring, can
  produce a false gate match on stale scrollback. It remains for isolated-string checks and tests;
  the canonical live path is `classify_screen`, and the legacy scan should not be used to make a
  fire-taught-rule / escalate decision.
- **The forged-last-match residual family in `state_parser.py`.** The last-match invariant is
  correct and preserved; its provenance gates (`is_genuine_sector_status`,
  `is_genuine_port_report`, `sector_from_command_prompt`, and the unanchored
  `_YOU_HAVE_CREDITS_RE` balance read) are **shape** checks, not identity checks. A forged in-band
  line landing *after* the genuine one on the same settled screen can win last-match. This is a
  documented residual, bounded today by solo play and slated for a single unified
  anchor-to-live-prompt / exclusivity hardening before any autonomous run on a multiplayer or
  shared server — recorded here, not silently reconciled.
- **`parse_state()`'s per-cycle consumers (archive-only — do-not-revive).** The pre-rebirth run-loop
  that read this structured state and could pick a per-cycle EV keystroke off a *recognized* class
  rather than only playing a taught macro lived in archive `twclient/autopilot.py`. Tip has **no**
  `autopilot.py` outside `archive/` — it is gone from the live import tree, not merely deprecated in
  place. That historical divergence from the reborn taught-behavior contract is owned and recorded by
  [The App Autopilot Model](/architecture/app-autopilot-model.md), not here. This concept only
  produces the semantic read; it never selects an action, and nothing in these read modules should
  be changed to do so.

# Examples

A settled screen and the read it produces:

```
Rendered (settled):
  Sector  : 5678
  Ports   : Hammurabi Annex, Class 2 (BSB)
  Warps to Sector(s) :  (379) - (597) - (1302)

  Command [TL=00:14:33]:[5678] (?=Help)? :

classify_screen(full_text, prompt_line="Command [TL=00:14:33]:[5678] (?=Help)? :")
  -> "main_command"          # gate anchor on the prompt line

parse_state(full_text)
  -> { "sector": 5678,       # LAST line-start "Sector : N"
       "port": {"class": "BSB"},
       "warps": [379, 597, 1302] }
```

An unknown screen — the stop-and-handoff trigger:

```
Rendered (settled):
  The ancient vault door bears a single riddle, and a blinking cursor.
  Speak the word:

classify_screen(...) -> "unknown"     # no anchor matches
  => autopilot STOPS, keyboard to the human (Control & Escalation owns the handoff;
     typed STOP codes / `<code>:<detail>` qualify shape → `halt_reasons.py`,
     labels → `cockpit/stopbanner.py`)
```

Stale-scrollback, why last-match is load-bearing:

```
Rendered (settled), stale value above the live one:
  We'll sell them for 132 credits.        <- stale port offer, still on the grid
  ...
  You have 100,485 credits                <- the real, current balance

first-match  -> credits = 132      (WRONG — corrupts a reward delta by +90,661)
LAST-match   -> credits = 100,485  (correct)
```

# Citations

[1] `tw2002_aiclient/session/classify.py` — gate/content anchor split, prompt-line discipline, `cim_report` and
    `game_select` exclusivity hardening, `is_probable_secret_prompt` redaction predicate
    (ported from archive `twclient/classify.py`).
[2] `tw2002_aiclient/session/state_parser.py` — last-match invariant, line-shape provenance, block-scoped
    commodity reads, `sector_from_command_prompt`, the documented forged-last-match residual family.
[3] `tw2002_aiclient/session/terminal.py` — the fixed 80×25 pyte grid (no scrollback), CP437 decode, cropped
    render — the substrate the stale-scrollback discipline exists to survive.
[4] `tw2002_aiclient/menu/sig.py` — the shared, dependency-light menu-signature primitive
    (archive name `twclient/menu_sig.py`).
[5] CLAUDE.md "Hard rules" — `wait_prompt` case-sensitivity, `state_parser` last-match, secrets
    never touch logs/argv/repo, single-connection pidfile.
[6] `.samantha/plans/okf-final-vision-map.md` — `engine/screen-understanding.md` spec
    (must-cover, cross-links, CARRY-WITH-CHANGES A6/A7 disposition).

- **Interop patterns (required):** [TW2002 Screen Patterns](/research/tw2002-screen-patterns.md) — P-BLOCK, P-QTY, P-GATES, P-PORT-MASK, P-BANNER, …
