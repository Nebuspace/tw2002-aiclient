---
type: Decision Log
title: DECISIONS — Open Questions
timestamp: 2026-07-24T00:08:22Z
---

# DECISIONS — Open Questions

<!--
This is the open-questions workspace. It is the first stop when Samantha (or Monk)
hits a canon edge: a Gap (no canon covers it), a Conflict (action would contradict canon),
or a Change (canon itself appears wrong or stale).

LIFECYCLE:
1. Log the question here (OPEN) — do not stall; build the unambiguous kernel and continue.
2. Samantha drives the discussion with the human.
3. Human resolves → mark RESOLVED, draft an ADR if the resolution is durable.
4. Ratified ADR → entry here moves to CLOSED; canon is updated; the leash grows.

RULES:
- Append-only within each item once logged. Never delete or overwrite an open item.
- The human is the only one who can mark something RESOLVED or CLOSED.
- A DECISION logged here is NOT yet canon — act on the unambiguous kernel only.
- Items stale beyond 2 sprint cycles → flag to the human for triage.
-->

---

## OPEN

<!-- Items not yet resolved. -->

### OPEN-PLAY-STATUS-MIDSTRIP — SUPERSEDED 2026-07-31

**Superseded by** `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`: App `status_line` / offers paint in **LOGS**, not a mid control-strip segment. Calm teachband is the trainer key row (E/P/L/T/C/S), not A/R/T.

### PENDING-HUD-CARGO-HOLDINGS-SHIP-INFO — ship-info per-commodity hold lines (2026-08-08)

**Edge:** Change — trade-path sticky Ore/Org/Equ shipped (`WO-HUD-CARGO-HOLDINGS`, #306); ship-info lines that name per-commodity holds are **not parsed yet** (no fixture shape — see `trainer-cockpit.md` cargo blurb).

**Kernel (still open):**
1. When ship-info prints Ore/Org/Equ hold lines in fixtures/live, parse into session sticky holdings (same honesty contract as trade writes — never from port market rows).
2. Until that shape exists, trade buy/sell remains the only holdings writer; HUD shows trade-derived holdings only.

**Status:** Pending — trade-path wave shipped; ship-info parse deferred.

**Update 2026-08-14 (staleness check).** Re-affirmed Pending — tip still has no ship-info
Ore/Org/Equ fixture shape and no product parser into sticky holdings; trade buy/sell remains
the only holdings writer (`WO-HUD-CARGO-HOLDINGS` / #306). Open since 2026-08-08; keep on the
2-sprint triage radar but do **not** age-out silently — next step is a fixture-backed build WO
when a real ship-info hold-lines sample exists, not a decline. Kernel above unchanged.

### PENDING-CHAIN-HUNT-SIBLING-EXHAUST-DEPTH-TURN-CAP — Chain-hunt numeric defaults (2026-08-09)

**Edge:** Gap — `canon/strategy/exploration-policy.md` adds the **Chain-hunt** intent
(sibling-exhaust + ancestor-port backtrack, ~2× hop-cost vs Map-fill) as net-new strategy canon.
Mechanism shape is specified; **numeric defaults** for how far / how long a single armed Chain-hunt
run may go are not — hard-coding them in a follow-on build WO would invent operator-facing budgets
without a ruling.

**Kernel (unambiguous without the numbers):**
1. Chain-hunt planner shape (closed sibling set at a confirmed-port anchor; return after flyby;
   recurse on port neighbors; backtrack to nearest ancestor port with open siblings; do not use
   Map-fill densest-reachable recovery while an ancestor still has open siblings) may be drafted and
   reviewed as canon.
2. **Planner + CLI/daemon arming is LIVE on tip** (`plan_chain_hunt` / `INTENT_CHAIN_HUNT` /
   `tw explore start --intent chain_hunt` with **required** caller-supplied
   `--exhaust-depth` / `--turn-budget` — PR `#640` / `#641`). Play E stays 2-wide; Chain-hunt is
   deliberately not on the panel cycle ([exploration-policy](/strategy/exploration-policy.md)
   Schema · Code divergence closed 2026-08-10). This Pending does **not** authorize inventing
   built-in depth/turn **defaults** in code — omit-until-ruled; fail closed if the caller omits
   the required flags (already tip behavior).
3. Map-fill G1 nearest-first behavior remains correct for Map-fill; Chain-hunt must not silently
   reuse that pick as if it were chain-aware.

**Needs human ruling before shipping defaults (not before arming):**
- **Sibling-exhaust depth default** — optional built-in max recursion / anchor-stack depth when the
  operator does not pass `--exhaust-depth` (today: no default; flag required).
- **Turn-budget default** — optional built-in max turns / hop proposals when `--turn-budget` is
  omitted (today: no default; flag required), acknowledging the ~2× hop-cost tradeoff vs Map-fill.

**Status:** Pending — **numeric defaults only** remain human-gated; mechanism canon + tip wiring
shipped (exploration-policy · `#640`/`#641`). Do not re-open as "Chain-hunt CLI unbuilt."

**Refs:** `workorders/WO-CANON-DRAFT-CHAIN-MAXIMIZING-EXPLORE-STRATEGY.md` ·
`workorders/WO-CANON-FIX-DECISIONS-CHAIN-HUNT-WIRED-TIP-TRUE.md` ·
`canon/strategy/exploration-policy.md` § Chain-hunt · `canon/strategy/trade-loops.md` cross-link ·
origin Max sector-5/6/7/8 walkthrough 2026-08-09 · tip `explore.py` / `session/cli.py`.

### PENDING-AFFORDABILITY-EXPLORE-WEIGHT-DEFINITION — credits-cross-cost explore nudge (2026-08-09)

**Edge:** Gap — `canon/engine/priority-engine.md` and `canon/strategy/exploration-policy.md` add
**affordability** as a second OR-cause of the shared `explore_appetite_raised` FOCUS ranking input
(credits clearing a known hold-upgrade and/or fighter cost → louder explore suggestion). Mechanism
shape is specified (reuse existing flag + `afford_fighters` math surface; never autonomous switch).
**What counts as "affordable"** and whether the two cost surfaces nudge with different strength are
not fixed — hard-coding them in a follow-on build WO would invent operator-facing thresholds without
a ruling.

**Kernel (unambiguous without the numbers):**
1. Affordability MAY raise explore's FOCUS `overlay_weight` / set `explore_appetite_raised` when
   credits clear a **known** quote — omit-until-known; never invent prices.
2. Depletion and affordability share **one** signal (`explore_appetite_raised`) and one FOCUS
   consumer — do not mint a parallel appetite boolean.
3. Ranking / suggestion only — never autonomous rotation off a running loop, never live-drive
   (same invariant as depletion appetite and [trade-loops](/strategy/trade-loops.md) depletion STOP).
4. Implementation wiring (`afford_fighters` → `focus_status.recommend_focus_candidates` reader for
   the existing flag) stays a **follow-on build WO** after this canon draft is reviewed.

**Needs human ruling before build:**
- **Affordability definition** — raw `credits ≥ hold_upgrade_quote` / `fighter_unit_price`, or a
  safety-margin buffer above reserved trade float (and how that float is measured)?
- **Differential weighting** — should clearing a hold-upgrade quote nudge explore stronger than
  clearing a fighter purchase (hold upgrades being cheaper / more directly loop-enabling), or one
  shared boost when either threshold clears?

**Status:** Pending — threshold definition human-gated; mechanism canon in priority-engine +
exploration-policy (this WO).

**Refs:** `workorders/WO-CANON-DRAFT-AFFORDABILITY-EXPLORE-WEIGHT.md` ·
`canon/engine/priority-engine.md` § FOCUS ranking input — affordability ·
`canon/strategy/exploration-policy.md` § Explore / exploit appetite ·
`chain_depletion.py` ~148–165 (`explore_appetite_raised`) · origin Max credit-threshold framing
2026-08-09.

---


## RESOLVED

<!-- Items with a human decision on record. Waiting for ADR drafting or already captured. -->

### RESOLVED-HUD-CARGO-BREAKDOWN-EMPTY-TOTAL — CARGO empty/total occupancy (2026-08-01)

**Edge:** Change — `trainer-cockpit.md` said CARGO is **empty holds only**; Max (2026-08-01) asked the right HUD to explain hold occupancy. Bare `CARGO 50` reads as contents.

**Ruling (Max product ask = GO for display honesty):**
1. CARGO paints **empty and total** when ship-info `Total Holds : N - Empty=M` is known (filled = N−M is implied, not a third invented claim).
2. Port-commerce empty-only lines still update empty; do not invent total from port **market** commodity rows.

**Shipped:** `WO-HUD-CARGO-BREAKDOWN` → `9b78c57` (#305) — `hud_tracking.format_cargo_hud_value`, `Session.observe_cargo`, trainer-cockpit cargo blurb. Trade-path per-commodity holdings → `ad0aff8` (#306); ship-info parse remains open as `PENDING-HUD-CARGO-HOLDINGS-SHIP-INFO` above.

---

### RESOLVED-DEV-DRIVE-EXCEPTION — narrow, sacrificial-only, manual AI live-drive for development (Max direct, 2026-08-07)

**Edge:** Change — every doctrine/engine doc in this bundle states without qualification that live keystroke senders are `{app, human}` only and the AI never sends one. Max asked directly for an exception scoped to development/debugging.

**Ruling (Max, 2026-08-07 — "You are OK live driving it if its for the purpose of development! Add that to canon!"):** clarified via follow-up question to exactly three conditions, all required simultaneously: (1) sacrificial account only (`crawl_sacrificial = true`), (2) manual, one action at a time — never a standing autopilot/loop/taught rule, (3) logged as a distinct third sender class, never folded into `app` or `human`.

**Canon home:** [dev-drive-exception](/doctrine/dev-drive-exception.md) (full schema + "what this
does not authorize" + Code divergence). Pointer addenda in [ai-teacher](/engine/ai-teacher.md) and
[alignment-and-conduct](/doctrine/alignment-and-conduct.md) — additive only, does not weaken the
`{app, human}`-for-play framing either document already carries.

**Status:** RESOLVED / code enforcement LIVE. Send-time gate shipped as
`WO-BUILD-DEV-DRIVE-SENDER-ENFORCEMENT` (`999ddc7`, 2026-08-08): tip
`VALID_SENDERS = ("app", "human", "dev")` + `crawl_sacrificial` gate on every `dev` send — see
[dev-drive-exception](/doctrine/dev-drive-exception.md) § Code divergence. Residual there is the
CLI `--sender` surface (also LIVE, still sacrificial-gated), not an unbuilt third sender.

**Update 2026-08-15 (staleness check).** Prior Status/Canon-home prose said "canon-only today —
no `VALID_SENDERS` third value / follow-up WO not yet filed." Tip-false since `999ddc7`; ledger
lines above corrected to match the doctrine Code-divergence section.

### RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES — two operator modes (Max ratify 2026-08-01)

**Edge:** Change + Conflict — Max clarified the trainer mental model; live Play had conflated Explore gather with Trade Loop execution.

**Ruling (Max, 2026-08-01 — “ratify”):**

1. **Explore mode (`E`)** — FOCUS is **discovery**: StarDock, sector special formations, planets, and **mapping / learning** Trade Loop Chains. Not money-path execution of those chains. Docking under Explore is world-model sampling only.
2. **Trade Loop Chain execution (`T`)** — separate mode: warp to the **L-selected** chain’s start sector, then warp the loop sector-by-sector **actually trading** at each port.
3. **`L)ist Loops`** — selects which discovered/taught loop is **armed** for execution.
4. **`P)ort Trade·ON`** — gates whether Trade Loop **execution** may spend money. It is **not** the switch for Explore gather docks (decouple `dock_new_ports` from Port Trade).
5. App-armed must **not** silently auto-execute Trade Loop Chains from FOCUS while Explore is the discovery path. Execution is **T** (and L selection), with `P` as the money gate. Under APP-ARMED, T may run without per-action `y` when `P` is ON (trainer auto default stands for the T path).

**Supersedes / narrows:** `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 6 auto-fire for `run_chain` must not mean “FOCUS bubble fires trade during Explore.” Cargo/Ship upgrade auto-fire unchanged by this ruling.

**Canon:** Amend `mode-line-and-teach-controls.md` (+ trainer-cockpit as needed). Code waves: `WO-EXPLORE-TRADE-MODE-SPLIT` (decouple P/dock · stop FOCUS trade auto-fire · wire T to L-selection · allow L-select under partial discovery · soft truncated start when fingerprint present).

**Public-safe.**

### RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731 — trainer Play chrome + App-armed default (Max 2026-07-31)

**Edge:** Conflict + Change — calm strip / seat+arm / CONN / panic / money-path confirm-not-auto vs Max trainer model.

**Ruling (Max, session 2026-07-31 — “Proceed”):**

1. **Seat:** One chip with Mode key — `^A)APP-ARMED` / `^A)MANUAL-HUMAN`. Merge APP+ARM. Halt = leave App → Manual (STOP/PANIC redundant as operator controls).
2. **Calm keys:** `E)xplore` · `F)ind StarDock·ON/OFF` (default ON) · `P)ort Trade·ON/OFF` (default ON) · `L)oops` · `T)rade Loop Chain` · `C)argo Hold Upgrade·ON/OFF` (default ON) · `S)hip Upgrade·ON/OFF` (default ON). Retire A/R/T/V/U/H/O/Panic from calm band.
3. **CONN:** Top line beside server/host; **green slowly flashing** when connected — not bottom strip.
4. **Outcomes:** `status_line` → **LOGS** (not mid-strip).
5. **Left gutter:** GOALS outer box with **FOCUS nested inside**; tall **FORMATIONS** panel down toward LOGS.
6. **Automation:** **App-armed auto = default** (trainer). Soft confirm-only banked. Per-action `y` is not the calm default under APP-ARMED + ·ON policies.

**Code waves:** `WO-PLAY-STRIP-TRAINER-CHROME` → `WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS` → `WO-PLAY-STRIP-POLICY-AUTO`.

**Canon:** Amend `mode-line-and-teach-controls.md`, `trainer-cockpit.md`, arm/seat prose as WOs land. Soft confirm (A) remains optional later — not ship path.

**Public-safe.** No credentials.

---

Append to `tw2002-aiclient/canon/DECISIONS.md` (RESOLVED — Max oral GO 2026-07-28 evening).

---

## RESOLVED-COMBAT-AUTOFIGHT-90 — NPC toll auto-Attack when force_share ≥ 0.90 (2026-07-28)

**Question:** May the fighter-toll guard autonomously Attack on NPC encounters, and at what threshold?

**Ruling (Max):** Yes for **NPC/environmental** tolls only. Use **`force_share = own / (own + enemy)`**. Autonomous Attack iff `force_share ≥ 0.90` (≈9:1) **and** enemy count within `winnable_enemy_band` (default ≤3) **and** both counts are present. Else Retreat. Never Pay. PvP ⇒ STOP. Unparseable ⇒ Retreat. Quantity prompt after Attack is in scope.

**Canon:** Amend `/strategy/toll-and-defense.md` (schema + I5 guard + divergence). Prior reborn prose that framed *all* engaging combat as human-only STOP is superseded for this gated band only.

**Code:** EXEC `WO-COMBAT-ENCOUNTER-POLICY-EXEC` aligns `fighter_toll_policy` to force_share (replace weaker parity auto-Attack).

**Public-safe.** No credentials.

## CLOSED

<!-- Items fully absorbed into canon (ADR accepted + canon updated). Safe to archive. -->

### OPEN-003 — Config Bootstrap host/port: `profiles.toml [default]` literal vs server-catalog resolution — CLOSED

**Filed:** 2026-07-24
**Filed by:** Samantha (impl-claudecode-aiclient), via WO-P2-020 Wave-1 review
**Edge type:** Conflict (canon text vs greenfield config schema)

**Question:**
`canon/architecture/session-engine.md` Config Bootstrap specifies the host/port precedence ending in
`config/profiles.toml [default]` — implying host/port are read *directly* from the `[default]`
profile. But the greenfield config schema (`config/profiles.toml.example` + `config/servers.toml` +
`tw2002_aiclient/session/credentials.py`) models a profile's connection coordinates PRIMARILY via a
`server` field — a catalog key into `servers.toml`, documented as *preferred* — with `host`/`port`
only as optional overrides; `credentials.list_profile_summaries()` already resolves
profile → server-catalog → host/port. WO-P2-020's `env.py` implemented canon's literal text (a direct
`[profile] host/port` read), which **cannot resolve the preferred `server = "…"` profile shape** (it
hard-errors on it) and stands up a *second* host/port resolver diverging from `credentials.py`'s
catalog-aware one.

**Why it matters:**
The daemon (`env.py`) and the TUI profile-picker (`credentials.py`) would disagree on where a profile
connects; a catalog-only profile — the documented *preferred* shape — can't be daemon-resolved. Two
divergent resolvers for the same fact is a latent inconsistency bug.

**Options considered:**
- **A (recommended):** `env.py`'s `profiles.toml` fallback resolves THROUGH the server catalog (reuse/
  mirror `credentials.py`): profile → `server` key → `servers.toml` host/port, explicit `host`/`port`
  as override. Update canon Config Bootstrap to state the catalog indirection. One resolver; honors the
  schema's preferred field; a superset of canon's current text.
- **B:** Canon is literal — daemon host/port bootstrap reads `profiles.toml [default]` host/port
  directly; the server catalog is a TUI-only concern. (Contradicts `profiles.toml.example` naming
  `server` the preferred field.)

**Unambiguous kernel built while waiting:**
WO-P2-020 proves via the CLI/env tier (`TW2002_HOST`/`TW2002_PORT`) — which canon and schema agree on
and `env.py` implements correctly; the fake-harness proof does not exercise the
`profiles.toml`-vs-catalog branch. Monk-A's canon-literal `env.py` fallback is retained as-is
(conformant to canon's *current* text); no divergence silently "fixed." Resolution (Option A) is a
follow-on refinement WO, not a 020 blocker.

**Staging (2026-07-24 — WO-OPEN-003-DOCS, hub):** Hub leans **Option A** (one catalog-aware
resolver; `servers.toml` preferred per greenfield schema). Execute stub:
`workorders/WO-OPEN-003-host-port-resolver.md`. Related seam: `workorders/WO-TW-CONFIG-DIR.md`.

**Option A execute (shipped `da1c875`):**
1. **One catalog-aware resolver.** `credentials.resolve_profile_host_port` — profile → optional
   explicit `host`/`port` override → else `server` key → `config/servers.toml`. `env.py` / `cli.py` /
   `protocol.py` / `credentials.list_profile_summaries` all delegate (four resolvers collapsed).
2. **Typed errors.** `ProfileConnectionError` subtypes (`ProfileNotFound` / `ProfileIncomplete` /
   `ProfileMalformed`).
3. **`TW_CONFIG_DIR`.** Additive env seam on credentials config paths; zero change to env-first
   password / chmod-600 / redaction.
4. **Canon.** `session-engine.md` Config Bootstrap states catalog indirection + shared resolver.

**Resolved (2026-07-25T13:13:55Z) — CLOSED.** Max formal CLOSE (hub relay `@ 13:13:55Z`): Option A
already shipped `da1c875`; DECISIONS item CLOSED. No further ADR owed — canon + product already
aligned.

<!-- (end OPEN-003) -->

### OPEN-002 — Commit remaining untracked `canon/**` / `workorders/**` — CLOSED

**Archived.** Full thread → [DECISIONS-archive.md](DECISIONS-archive.md#open-002--commit-the-remaining-untracked-canon--workorders-bundles--closed).
Durable outcome: hub GO'd explicit-path bundle commits (`e2fda40` + WO-WORKORDERS-BUNDLE-COMMIT).

### OPEN-001 — One package tree vs Phase-0 two-package scaffold — RESOLVED/CLOSED

**Archived.** Full thread → [DECISIONS-archive.md](DECISIONS-archive.md#open-001--one-package-tree-vs-the-phase-0-two-top-level-package-scaffold--resolvedclosed).
Durable ruling: [ADR-001](ADR/001-one-tree-embedded-session.md) Accepted 2026-07-24 — one tree,
`session/` subpackage, exit-popup default **No** (leave daemon running).

## Accepted — retire root DESIGN.md + priority_engine.md into OKF (Max 2026-07-25T21:21:27Z)

**Ruling:** Fold repo-root `DESIGN.md` and `priority_engine.md` into `canon/` OKF and delete them from the git repo root. No architecture/strategy markdown at root.

**Disposition:**
- `DESIGN.md` — technical content already owned by session-engine / cli-verbs / settle-detection / north-star; MCP-ready-by-construction note folded into session-engine; AI-native-driver framing stays superseded.
- `priority_engine.md` — already reimagined as `canon/engine/priority-engine.md`; citations retargeted; root deleted.

See `WO-ROOT-MD-INTO-CANON`.

## Accepted — extract research patterns into OKF (Max 2026-07-25)

**Ruling:** Extract useful patterns from the helper + TWGS research findings into
`canon/research/tw2002-screen-patterns.md`. Inform Implementers via
`workorders/BRIEF-OKF-SCREEN-PATTERNS.md`. Raw dumps under `research/` are redirects;
`research/raw/` stays gitignored corpus only.

## Accepted — sole docs root: no `docs/` tree (Max 2026-07-25T21:03:14Z)

**Ruling:** Delete `docs/`. Fold its content into the OKF bundle under `canon/`. No second documentation tree.

**Disposition of current files:**
- `docs/OPERATOR.md` → fold into OKF surfaces/architecture (entry + CLI / session cold-start) as prescriptive operator-facing concept prose — not a parallel guide.
- `docs/community-sources.md` → new or extended canon concept under doctrine (or engine) for public catalog sources + honesty policy.

**Do not** grow a non-OKF docs dump. README may keep a short pointer into `canon/` only.

## Accepted — archive-port-patterns research doc (Max GO this session · 2026-07-25T21:53:00Z)

**Decision:** Extract pre-rebirth archive patterns into `canon/research/archive-port-patterns.md` as an OKF Reference concept. Archive stays reference-only; no code restored to root. 14 patterns (AP-01…AP-14), 8 negative/do-not-port items. `canon/index.md` gets a Research section. Cross-links added to 4 existing concepts. Implementer brief at `workorders/BRIEF-OKF-ARCHIVE-PORT-PATTERNS.md`.

## Accepted — Max carte blanche parked gates (hub-ruled 2026-07-26 · Max: "carte blanche for you to decide")

Max delegated the standing 🧑‍⚖️ parked gates to hub (Samantha). Treat the following as **Accepted** human rulings (delegation = human resolution). Seats align; do not re-litigate without a new Max ask.

### A — Classify vocab + money-screen + tip land (was WO-CLASSIFY-BLOCK-TITLES)

1. **Add** closed-vocab labels `stardock_cargo_hold_quote` and `stardock_shipyard_listing` (content anchors; exclusivity / provenance discipline — same family as `cim_report` distrust-of-bare-shape).
2. **Add** gate-class `money_prompt` for quantity/money/bank-transfer style blocking prompts. **Hard pin: never-auto-action** — App must escalate; no rule/macro may fire; crawler `_UNSAFE_SCREEN_PATTERNS` (or successor) must cover; aligns P-QTY.
3. **GO land** `preserve/classify-parked` aligned to (1)+(2); update `screen-understanding.md` vocab list in the same tip.

### B — ASCII / glyph under `LC_ALL=C` (crash vs silent hole)

**Prefer honest substitute or controlled loud failure over silent content holes.** ASCII mode may use the documented TW-safe substitute table (`+|-/` etc.). Em-dash and other non-encodable glyphs: substitute per table **or** fail the write with a typed/logged error — never drop characters with a successful-looking send. Silent holes are the defect.

**Tip home:** `tw2002_aiclient/session/tty_encode.py` — `substitute_for_tty` / `encode_for_tty` apply the operator-glyph substitute table and retry; still-unencodable → raise `UnicodeEncodeError` for a loud CLI ERROR (never `errors="ignore"`). Module cites this §B / WO-ASCII-ENCODE-HONESTY. Product choke under non-UTF-8 stdout for ★ / em-dash / … on some CLI paths remains **BANKED** as `CLI-ASCII-WRITE-CHOKE` in [findings](findings.md) (STAGED pending Max glyph ruling) — the encode helper is the contract; wiring every writer is separate.

*(Honesty pass `AUDIT-CANON-DRAFT-TTY-GLYPH-TABLE-CROSSREF`, 2026-08-04.)*

### C — Secrets surfaces (`repr(UnicodeDecodeError)` / `get_password` / stuck-login wire)

**GO rehab:** decode/permission failures → typed redacted errors; **never** put secret or undecoded secret-adjacent bytes into `repr()`, exception strings, CLI JSON, or logs. `get_password` failure → `None` or typed error without payload leak. Stuck-login RX-on-wire stays redacted. Orthogonal to ensure-JSON MT-07 (already separate).

### D — Settle default ownership (prompt settle)

**Settle-detection owns readiness** ("is the stream settled / safe to act"). **Screen-understanding owns identity** ("what screen is this"). Drive verbs (`do`) take settle-detection's prompt-line + `rx_count` / freshness discipline as default `match_scope`; classify vocab does **not** set settle readiness. Closes the open note under P-SETTLE-LINE.

### E — Catalog public names + `twgs.exiled.org`

1. **Keep** third-party BBS directory display names (including Firstname-Lastname shapes) as published catalog provenance — not a privacy scrub target in this public-game-directory sense.
2. **Keep** `twgs.exiled.org:2002` with honest `archive_seed` / known-exception status (do not drop). Operator may still use it; catalog must not lie that it was absent from greenfield when it was not.

### F — Throwaway-worktree lifecycle (Proposed → Accepted with CC amendments)

Accepted: owner removes on Accept/abandon; `preserve/<wo-id>` if tip ∉ origin; hub mass-prune only after `🧹 PRUNE-INTENT` + seat ACK; **never remove a LOCKED worktree** (lock carries PID; `kill -0` detects stale); soft ceiling **12 is a reporting trigger**, not a removal trigger (CC amendment B). Hub may lift 🧹 PRUNE PAUSED after seats ACK this Accept note.

### six-archived-modules-reroute-vs-fight-ev — RULED: build the EV ranking function, coaching-only, never auto-firing (hub 2026-08-05 · Max carte blanche)

**Ruled:** the reroute-vs-fight EV comparison that six canon docs (`app-autopilot-model.md`, `priority-engine.md`, `exploration-policy.md`, `candidate-mining.md`, `action-safety-guards.md`, `screen-understanding.md`) name is **scheduled to be rebuilt** — as a pure ranking/scoring function feeding the existing priority engine and coach card, **never** as an auto-firing decision-maker. This resolves the design-scope half of the citation-hygiene escalation (the citation half already landed via PR #431, remapping the six docs' stale `twclient/*.py` references to live paths).

**Scope, precisely:** the function computes and *ranks* candidate actions by expected value; it surfaces the top-ranked option to the coach card / replay UI for the human to act on. It does **not** select, queue, or execute any action on its own — that would violate this repo's foundational invariant (`AI never live-drives`, live senders are `{app, human}` only). If a later WO's implementation drifts toward auto-selection under any framing (e.g. "auto-apply the top-ranked reroute"), that's a new escalation, not covered by this ruling.

**Why build now:** the 2026-07-23 rebirth archived the old `twclient/autopilot.py` / `priority_engine.py` / `loop_player.py` run-loop wholesale with no successor for the run-loop/priority-select surface — six docs describing this in present tense were describing dead code, not live behavior (now fixed per PR #431). Leaving the feature permanently unbuilt would mean six canon docs keep describing a target that never arrives; building the coaching-only kernel closes that gap without reintroducing any live-driving risk.

**Owner:** impl-aiclient-cursor / impl-claudecode-aiclient (whichever seat picks it up).
**Ref:** `canon/architecture/app-autopilot-model.md`, `canon/engine/priority-engine.md`, `canon/strategy/exploration-policy.md`, `canon/strategy/candidate-mining.md`, `canon/doctrine/action-safety-guards.md`, `canon/surfaces/screen-understanding.md`; PR #431 (citation half).

**Correction (hub 2026-08-05 · Max direct clarification, same day):** the "coaching-only, never auto-firing" framing above overstated the constraint and is **superseded** by this note. Max: *"AI live driving is not the same thing as autopilot acting and firing programmatically — we are OK designing autopilot automation into aiclient that takes that kind of action even against another human. The human learns by watching the action and then later by the report [...] provided post-session of what happened."*

The invariant this repo actually holds is `AI never live-drives` — the **AI/LLM teacher** never reasons live over the next keystroke (`north-star.md` lines 26-34: "Zero AI reasoning runs per cycle"). That is a hard, unchanged rule. It does **not** forbid the **`app` layer** — the deterministic, taught/armed autopilot — from executing a rule's action programmatically once that rule has been human-approved at teach/arm time, including firing against another human. `app` is a legitimate live sender in its own right (`CLAUDE.md:63`, "Live senders are `{app, human}` only"); "coaching-only" was never a real constraint on it.

So: the EV ranking function this entry authorizes may, once built out and wired to a taught/armed rule, drive an `app`-layer autonomous action — not just surface a suggestion to a human. What stays fixed: the *rule* is human-approved before it can fire (teach-time gate, not per-firing gate), and the AI/LLM itself never picks the live keystroke. Accountability for autonomous `app` action is a **post-session report**, not live per-firing approval — see the post-session-action-report entry below (**SHIPPED** on tip: `tw report` / `session_report.py`).

Any WO building this function should design for eventual `app`-layer auto-fire from the start (behind the existing teach/arm gate), not architect a coaching-only ceiling that would need to be torn out later.

### post-session-action-report — CLOSED / SHIPPED on tip (hub 2026-08-05 DOC-GAP · tip-closed 2026-08-06)

**Original gap (2026-08-05):** Max named a post-session accountability digest for autonomous `app`
action; DECISIONS staged a BUILD-WO while only pull-based `tw log`/`tw trail` existed.

**Tip (2026-08-06):** **LIVE.** `tw2002_aiclient/session_report.py`
(`build_session_report` / `format_session_report` / `write_session_report`) + CLI verb `tw report`
(daemon-free ledger read; emphasizes `actor=app`; optional `--out` file). Canon home today:
[trace-ledger](/engine/trace-ledger.md) fifth-consumer bullet. A dedicated OKF concept stub
(`WO-CANON-DRAFT-POST-SESSION-REPORT-STUB`) remains optional Max-gated follow-on for index
discoverability — not blocking this BUILD row.

**Residual (not this WO):** unprompted session-end auto-print is still optional delivery polish;
primary surface is on-demand `tw report` as shipped.

### 2026-08-05 batch — Max carte blanche on aiclient gated-queue rulings

Max: "Carte Blanche to make the decisions for aiclient." Applying the same pattern as the earlier Sectorwars2102 batch this session: rule → log here → build unblocks; the hard safety list (AI-safety/autonomous-money-path code, new deps, secrets) stays Max-gated regardless of the general grant — those items are left Pending below with the reasoning for why, not ruled on.

**Ruled (unblocked, queue rows updated):**

- **`WO-ESCALATE-TRADE-DRIVER-CHAIN-RUNNER-SCREEN-MATCH-NO-CANON`** — Option C: have an implementer read `trade_driver.py`'s `run_chain()` internals first and report back whether per-hop `screen_match` re-validation already exists. This is fact-finding, not a design call yet — if the report comes back ambiguous, it re-escalates for a real ruling; if it's clearly (A) or (B), the implementer's own finding closes it without a second round-trip.
- **`WO-ESCALATE-DRAFT-APPROVE-UNBRIDGED-BACKLOG-NO-CANON`** — Option A: leave as-is, no expiry/visibility surface needed. Rare enough in practice (an approved-but-never-bridged draft) not to warrant new UI or a TTL policy; revisit only if it becomes a live operator complaint.
- **`WO-ESCALATE-FIGHTER-UNIT-PRICE-UNVERIFIED`** — keep the canon hypothesis name `FIGHTER_UNIT_PRICE_CLASS0` Planned-only / explicitly unverified (tip code uses a separately named placeholder `FIGHTER_UNIT_PRICE_DEFAULT` in `session/explore_defensive_posture.py` — do not treat either as a measured Class-0 quote). Do not encode a guessed number into priority-catalog rows #6/#7; those stay blocked until the real TW2002 fighter price is sourced from a live server, not invented.
- **`WO-ESCALATE-CLI-VERBS-DOC-VS-LIVE-MISMATCH`** — Option B: correct `cli-verbs.md` to stop presenting `replay/play/autoloop/haggle/autopilot/analyze/mine` as live `tw` subcommands when none are registered in `session/cli.py`'s `build_parser`. Wiring them for real (Option A) is deferred — several of the underlying engines (autopilot, haggle) are themselves still gated/partially-safety-adjacent, so wiring the CLI surface ahead of those individual rulings would front-run them. Fix the doc now; wire each verb through its own existing (or future) WO as that engine's gating resolves.
- **`WO-ESCALATE-TOLL-DEFENSE-UNBUILT-CONSTANTS`** — Option B: strip `keep_min_defense_fighters=20`, `shield_reserve_multiplier=2:1`, `missile_bypass_fraction≈7%` from canon as unconfirmed noise until a real design pass. Doc already self-flags `[hypothesis]` but still presents step-3 math as computable today — that's the part that's misleading and should go, not a build authorization for these specific numbers.
- **Port-economics floor/regrowth/plague numbers** (queue-aiclient.md:169) — mark permanently-unconfirmed in canon rather than investing in live per-server introspection right now. Same posture as the planet-colonization ruling below — third-party strategy-guide numbers don't get encoded as canon constants until someone actually measures them live.
- **Auto-haggle tuning defaults registry-migration** (queue-aiclient.md:170) — **DONE** (`WO-BUILD-HAGGLE-PARAMS-REGISTRY`, `37bf8bb` #575). Defaults now load from `data/haggle/params.json` via `tw2002_aiclient/haggle_params.py` (`round_cap=4`, `accept_threshold_pct=5.0`, `open_aggression_pct=15.0`, `verified_vs_live=true`); `session/haggle.py` consumes `DEFAULT_HAGGLE_PARAMS`. Per-server knob expansion remains optional future work; the registry substrate ships.
- **Toll resolver reserve floor / winnable-enemy-count band** (queue-aiclient.md:171) — verify-first: check whether code already exposes an override path before concluding it's hardcoded. If genuinely hardcoded, same LOW-priority registry-migration treatment as the haggle defaults above, not an urgent fix.
- **Ledger world_id: single-ledger Option A ratification** (queue-aiclient.md:188) — ratify Option A (single ledger, row-level `world_id` stamp) as the accepted design. It's already the de facto shipped implementation (`WO-PWO-090-LEDGER-WORLD-ID-STAMP`, merged `6244787` #366) with real behavior riding on it; this closes the missing paper trail, not a design change.
- **`WO-CANON-DRAFT-AUTOLOOP-RELAUNCH-ZERO-COVERAGE`** — proceed: draft canon coverage of `autoloop_relaunch`'s existing shipped semantics (`replays_from_start`, `sends_already_issued`) in `mode-line-and-teach-controls.md` alongside the existing `Spc` pause documentation. This is describing already-live, already-confirm-gated behavior — a doc-honesty fix, not new authorization for the replay mechanism itself (which already ships and is already confirm-gated).
- **3 stale citation/threshold doc corrections** (queue-aiclient.md:201) — proceed on all three: (1) correct `action-safety-guards.md`'s stale "still an open gap" note for floor_reached/credits_unreachable STOP-banner labels, since `stopbanner.py` already maps both (landed 2026-07-26, after the doc's timestamp); (2) correct the plain-English fighter-toll description to cite the real `force_share>=0.90` threshold instead of an implied 1:1 bar; (3) fix the `twclient/*` dead citation paths to their real `tw2002_aiclient/session|menu|loops` equivalents (or note no-tip-equivalent for `priority_engine.py`/`autopilot.py`, consistent with the reroute-vs-fight-EV ruling above — that module is scheduled to be (re)built, not falsely claimed to exist yet).
- **`WO-ESCALATE-PLANET-COLONIZATION-HYPOTHESIS-NUMBERS`** — mark explicitly NOT-BUILT/deferred in `planet-colonization.md`, same posture as port-economics above. Planet-colonization automation is not near-term in-scope; the doc should stop reading as ready-to-implement spec prose until someone actually measures live production/regrowth/plague numbers on a real server.

**Left Pending — stays Max-gated (hard safety-list carve-out, not covered by this carte blanche):**

- **`WO-ESCALATE-EXPLORE-BASELINE-EV-VS-NOVELTY-HALT`** / **`WO-ESCALATE-AUTOPILOT-EV-SELECTOR-VS-NOVELTY-HALT-CONTRADICTION`** / **`WO-FIX-EXPLORE-BASELINE-EV-NEVER-IDLE`** — AI-safety/autopilot-behavior precedence call (when the never-idle floor retires in favor of strict stop-on-unknown). This changes what the autopilot does when it doesn't know what's happening — squarely the kind of call that needs your eyes, not a design-scope default.
- **`WO-FIX-TRADE-DRIVER-RUN-CHAIN-ARM-GATE`** — autonomous money-path arm-gate hardening. Safety-list item by its own tag.
- **`WO-FIX-FIGHTER-TOLL-HUMAN-APPROVAL-GATE`** (and its duplicate at queue-aiclient.md:187) — combat/money-adjacent AI-safety: whether NPC-toll auto-Attack needs a per-fire human-approval gate on top of the existing force_share≥0.90 guard. Same reasoning as above — this is exactly the class of call the safety list exists to reserve for you.
- **3 DECISIONS.md entries "Pending Max Accept of prose"** (queue-aiclient.md:202, LOOPS/RULES-WORLD-MIGRATE-ON-READ, LEDGER-WORLD-ID-STAMP) — these are pure ratification-lag (code already shipped and matches), genuinely trivial, but "marking canonical prose Accepted" is the one canon-stewardship action this project's own convention reserves for a direct human nod rather than a design ruling. Flagging for your next pass rather than self-accepting — should take one line from you.

### Max 2026-07-29 — no invented defaults on draft→kernel bridge (WO-CANON-DRAFT-KERNEL-BRIDGE)

**Ruled:** when translating an Analyze/teach **draft stub** (`when`/`do`/`source`/`playback_eligible`)
into a fireable **kernel rule document** (`rule_id`/`screen_match`/`do`/`priority`), the bridge
**refuses missing human-owned fields** rather than minting defaults. Tip:
`cockpit/draft_approve.py::bridge_to_kernel_document` + identity-session collection.

**Why:** a defaulted `priority` would place every AI-authored rule at the same rank; the kernel
STOPs on ambiguous ties (`autopilot_ambiguous_rules`) instead of guessing — so inventing a default
turns "teacher proposed a draft" into "autopilot halts" at the moment the library becomes useful.
`rule_id` / `do` / `scope` are likewise human decisions, not teacher observations.

**Canon home:** [rule-macro-engine](/architecture/rule-macro-engine.md) § Draft stub → kernel document bridge.

### A.2 clarification — never-auto-action vs auto-haggle (hub 2026-07-26 · Max carte blanche)

**Ruled:** never-auto-action means **no unattended freestyle** on money/quantity screens — not a ban on **human-armed, guarded, taught** money-path rules.

- Unattended App / crawler / invent-a-keystroke: **still refuse** (`money_prompt` + `_UNSAFE` / `NEVER_AUTO_ACTION_CLASSES`).
- Human-armed autopilot with an explicit taught/guarded rule (auto-haggle answering `Your offer [N] ?`, bounded quantity chain steps): **exempt** — those concepts remain Accepted.
- `Your offer [N] ?` may stay unclassified as `money_prompt` (or later earn a dedicated haggle class that is auto-action-eligible when armed). Do **not** fold haggle offers into never-auto-action `money_prompt` without a new DECISION.

Harmless until a haggle/trade module lands; this clears the gate so one can.

### C.2 — Ensure screen-mirror / echoed credential (hub 2026-07-26 · Max carte blanche)

**Ruled:** Structured ensure diagnostics (screen mirror in error payloads, CLI JSON, logs, persisted reason strings) must **not** carry server-echoed credentials. Live TUI paint of the telnet stream may show what the server painted (human eyes on the game). MT-07 carrier 2 = **fix** (redact), not delete-xfail-as-design.

### C.2.1 — `tw status` prompt dual-use (hub 2026-07-26 · Max carte blanche)

**Ruled:** Split by **consumer**, not by one shared field meaning both things.

- **Live cockpit / HUD paint** may show the current prompt line (permitted live paint).
- **`tw status --json`** (and any structured spectator/export) must **not** echo credential-shaped or secret-prompt content — omit `prompt`, or replace with redacted / classification-only when secret-prompt heuristics fire. Classification stays.

Do not leave `"prompt": rows[-1]` feeding both sides unchanged. Thin follow-on WO OK.

**Correction (CC STATUS `a2e42d4`):** HUD does **not** read `status["prompt"]` — live paint is subscribe/`build_response` screen. Conflict was at the **verb boundary**, not two consumers of one field. Fix = stop structured `status` carrying a live-paint-only field. Heuristic redaction rejected (echoed credential fails `is_probable_secret_prompt` — unconditional omit).

### C.2.2 — `tw watch --json` (hub 2026-07-26 · Max carte blanche)

**Ruled:** `tw watch --json` is the **live-paint / subscribe export** by purpose — may carry full `build_response`-shaped screen events. Redirecting it to a file is an operator choice equivalent to capturing the terminal. Do **not** gut spectate under C.2.1. Document honesty in doctrine/cli-verbs when convenient.

### X1.1 — Current-sector sources (hub 2026-07-26 · Max carte blanche · CC X1 STATUS)

**Ruled:** For `state` / replay anchor checks, **only the command-prompt bracket** is admitted as current sector. The `Sector : N` status line is **not** admitted (warp-confirm / computer remote display ambiguity — wrong read satisfies the guard; missing read only halts). Widening requires a new DECISION + live warp-confirm capture — not fixture assumption. Aligns macros.md "missed write, never a wrong one."

## Pending — chain floors + class-derived posture (2026-07-27)

**Context:** Explore gate (#122) persists port **class** letter triples from flyby; `build_trade_hops` historically required non-empty `commodities` rows (docked commerce report). Reborn tree has no `commodities` producer and `write_port_only` has zero callers. Canon cites `MIN_CHAIN_LINKS` in `priority_engine.py`, which is not reborn; EV picker is out of scope.

**Decision (Pending Max Accept of prose if folded into FEATURES):**
1. Until a priority/EV layer is reborn, `MIN_CHAIN_LINKS` (and related floors) live as cited constants in `tw2002_aiclient/chains.py` with sole pure consumer `is_executable_chain`.
2. Trade-adapter / WIRE: support a **class-derived posture path** — emit a distinct, no-margin `trade_adapter.CandidatePair` from letter triples (WO-CHAIN-DETECT-WIRE correction: NOT a `chains.TradeHop` shape — `trade-loops.md` defines `TradeHop` as a *positive-margin* edge, and `CandidatePair` carries no margin field at all, structurally rather than merely `None`). `chain_detect.py` wires it to a **pair loop only** (two ports, set-intersection posture match + known route both ways) — no cycle search, `chains.py` untouched. Commodity/pct path (`build_trade_hops` → `chains.TradeHop`) remains for docked reports when that parser is reborn.
3. Follow-on WO: rebirth commerce-report parser + wire `write_port_only` (turn-spend prove).

**Refs:** #122 artifact correction · WO-CHAIN-DETECT-PORT · WO-CHAIN-DETECT-WIRE · CC 2026-07-27T23:31:10Z

## Pending — loops world-scope migrate-on-first-read (PWO-090 · hub GO 2026-08-03)

**ID:** `DECISION-LOOPS-WORLD-MIGRATE-ON-READ`

**Context:** `canon/engine/world-identity.md` requires the macro / loop library under
`state/world/<world_id>/skills/`. Pre-PWO-090 code used a flat `state/skills/` tree.
Hub GO (2026-08-03T12:56:30Z) required an explicit migrate-or-exempt DECISION — silent
empty-world reads against a non-empty flat store are forbidden.

**Decision (Pending Max Accept of prose if folded further into FEATURES):**
1. **Fresh installs** write/read `state/world/<world_id>/skills/` (+ `_drafts/`) when a
   `world_id` is supplied (product cockpit, `tw loops --world-id`, `tw record --world-id`,
   autoloop when a marked profile can form an identity).
2. **Legacy flat data** migrates **on first world-scoped read or write** via
   `migrate_flat_loops_to_world`: if the world store has no `*.json` and the flat store
   has any, copy files (including `_drafts/`) into the world path. **Idempotent.** Never
   deletes the flat tree (operator may remove later).
3. **Callers without `world_id`** (daemon-free tests, `tw loops` with no flag) keep the
   legacy flat path — no silent migrate without a world key.
4. Not a money-path / live-send change — filesystem scoping only.

**Refs:** hub GO PWO-090 · `loops/store.py` · `canon/engine/world-identity.md` §Code divergence.

## Pending — rules world-scope migrate-on-first-read (PWO-090 residual · hub GO 2026-08-03)

**ID:** `DECISION-RULES-WORLD-MIGRATE-ON-READ`

**Context:** Same class as DECISION-LOOPS-WORLD-MIGRATE-ON-READ. Reflex rules lived under flat
`state/rules/`; canon world-identity requires per-world durable stores. Hub GO 2026-08-03T13:12:30Z
chose rules over ledger for this residual (ledger HOLD — money-path audit trail).

**Decision (Pending Max Accept of prose if folded further):**
1. With `world_id`: `state/world/<world_id>/rules/` (+ `_drafts/`).
2. Legacy flat migrates on first world-scoped read/write via `migrate_flat_rules_to_world`
   (idempotent; never deletes flat).
3. Callers without `world_id` keep flat path.
4. Not a live-send change — filesystem scoping only.

**Refs:** hub GO rules-store · `rules/store.py` · loops precedent PWO-090.

## Accepted — ledger world_id row stamp (PWO-090 residual · hub GO Option A 2026-08-03)

**ID:** `DECISION-LEDGER-WORLD-ID-STAMP`

**Status:** Accepted (ratified 2026-08-05 batch — ledger world_id Option A at :308)

**Context:** Trace ledger remains a single append-only `state/ledger.jsonl` (passive
dispatch-trace sink — records decisions; never chooses a live keystroke). Hub GO
2026-08-03T13:29:00Z chose Option A over per-world path migrate (Option B held):
additive `world_id` stamp on new rows + filter on read. Money-path audit trail —
no rewrite/delete of existing rows.

**Decision:**
1. New rows may include `world_id` when the session can form an identity (profile-derived).
2. `read_entries(..., world_id=)` returns only matching stamped rows; unstamped legacy rows stay on disk and are excluded from filtered reads.
3. No per-world ledger path / migrate without a fresh proposal (Option B).
4. Never invent a slug; omit the field when unknown.

**Refs:** hub GO ledger Option A · `ledger.py` · world-identity.md global-sink note.

## DECISION-PWO-106-GENESIS-CONFIRM-SEAM (2026-08-03)

**Status:** Accepted (hub GO B-Option-A 2026-08-03T13:59:00Z)

Ship `genesis_confirm.genesis_send_if_confirmed` as the only choke-point for a future App Genesis send; reuse `cockpit.armconfirm` default-deny. No stub adapter in this WO (B-Option-B HELD).

## DECISION-PWO-107-SHIP-UPGRADE-DECISION-PORT (2026-08-03)

**Status:** Accepted (hub GO C-Option-A 2026-08-03T13:59:00Z)

Port archive TW-30 `ship_upgrade_decision` into `tw2002_aiclient/` as recommend-only; wire DECISIONS from `UpgradeDecision`. Purchase adapter (C-Option-B) HELD.


## DECISION-PWO-092-INTROSPECTOR-FIXTURE (2026-08-03)

**Status:** Accepted (hub GO Propose A 2026-08-03T15:20:00Z) · tip-amended 2026-08-06

Port archive introspector as pure text→rows; no live TWGS crawl or send.
Option A shipped. **Option B** (navigate/send to reach StarDock listing
screens for an active crawl) remains **HELD**.

**Amendment (PR #471 · 2026-08-06):** passive parse of already-on-screen
current-ship `I` info (`parse_current_ship_info` →
`Session.observe_current_ship`) is LIVE and is **not** Option B — no
navigation, no send. Distinct from opportunistic StarDock capture
(`game_data_capture`), which also never sends.

## DECISION-PWO-111-RX-REDACTION — RX transcript gate (2026-08-03)

**Status:** Accepted (hub GO Propose B 2026-08-03T15:22:00Z)

RX **transcript logging** reuses TX / ledger password-anchor (`password` RE) **or** post-`secret=True` operator-TX echo window → `log_redacted`. Live screen/`watch` paint residual remains named in `secrets-and-credentials.md` Code Divergence #1. No new match vocabulary; no parse/classify/session-control changes.

## DECISION-ADR-003-RESIDUAL-7-8 — Distributed-fold 6/8 residual items disposed (2026-08-09)

**Status:** Accepted (item 7 tracked process judgment) / **Accepted — shipped** (item 8,
2026-08-09 follow-through) — ADR-003 graduated to **Folded into trade-loops.md**

**Context:** ADR-003's index row (`canon/ADR/index.md`) cannot graduate from
**Distributed-fold: 6/8** to plain **Folded** by re-labeling alone — the lifecycle rule
requires the N→M gap to close "by shipping or by a tracked not-building judgment." Items
7 and 8 previously carried only a single pointer to
`workorders/WO-CANON-ROLLUP-ADR-003-DISTRIBUTED-FOLD-TAG.md` Accept #2, with no real
disposition. `workorders/WO-ADR-003-RESIDUAL-7-8-TRACKING.md` gave each a ruling; item 8
then shipped the same day.

**Item 7 — sacrificial live-prove gate (Accepted, non-blocking):** this is the standing
hub/Max merge-ritual live-prove process (`.cursor/rules/live-prove-pushback.mdc` /
`.cursor/rules/workorders-required.mdc` § Hub merge ritual), not an ADR-003-specific tip
module — it was never going to "ship" as code. It has already been concretely exercised
against this exact discovered-chain flow: `WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE`
(`Nebuspace/.samantha/coord/queue-aiclient.md`, ✅DONE — live-proven 2026-08-09 on the
`scout_academy` sacrificial profile, 6 instrumented cycles spending real turns/credits,
Δ≈1786cr/cycle). Tracked not-building judgment; does not block graduation.

**Item 8 — bounded-repeat contract (Accepted — shipped):** Max GO'd
`WO-BUILD-BOUNDED-REPEAT-TRADE-CHAIN-DRIVER` 2026-08-09 (answers the three scoping
questions as defense-in-depth: pass-count + per-re-arm floor + profit_target). Merged
PR #637 → main @ `22dfe7f3` (`tw2002_aiclient/bounded_repeat_trade_chain_driver.py`;
CLI `--pass-count` / `--profit-target`; sacrificial-only when `pass_count > 1`).
Supersedes `WO-CANON-DRAFT-BOUNDED-REPEAT-CONTRACT-SCOPE`. Default arm remains one-pass;
multi-pass is explicit. N→M gap closed → ADR-003 **Folded into trade-loops.md**.
The 2026-08-10 **Ratify as intentional** ruling is canon-honesty follow-through
(`DECISION-BOUNDED-REPEAT-TRADE-CHAIN-RATIFY` / this WO), not a re-open of those
scoping questions.

**Refs:** `canon/ADR/003-discovered-chain-approve-scaffold.md` § Status ·
`canon/ADR/index.md` · `workorders/WO-ADR-003-RESIDUAL-7-8-TRACKING.md` ·
`workorders/WO-BUILD-BOUNDED-REPEAT-TRADE-CHAIN-DRIVER.md` · PR #637.

## DECISION-PORT-FLOOR-CAPTURE-HOLD-RATIONALE (2026-08-09)

**Status:** Ruled (autonomous, carte-blanche 2026-08-09) — `port_floor_capture.py` stays analysis-only, never wired to write back into `port_economics.py`'s canonical hypothesis constants or any persisted world-model state. This is intentional, not stale scope-drift.

**Reasoning.** Verified `port_floor_capture.py`'s own results are always `verified_vs_live=False` — every estimate is synthetic-fixture-derived, none live-observed yet. Port-economics floor/regrowth/plague numbers were separately ruled 2026-08-05 as "permanently unconfirmed, mark in canon" — writing an unverified estimate back into any persisted/authoritative field would make it *look* confirmed to any downstream reader, contradicting that ruling's intent. This differs from `density_scan_capture`/`cim_report_capture` (both wired) because those write observed *live* data into the world model — `port_floor_capture` writes a *derived estimate over possibly-still-synthetic observations*, a different trust tier. Held back by design, not priority drift; revisit only if/when floor-price numbers get genuinely live-verified (a precondition, not a scheduling question).

**Refs:** `canon/strategy/port-economics.md` § Floor-price hypothesis / `port_floor_capture.py` ·
`workorders/WO-PORT-FLOOR-CAPTURE-HOLD-RATIONALE.md`.

## DECISION-BOUNDED-REPEAT-TRADE-CHAIN-RATIFY (2026-08-10)

**Status:** Ruled (Max, via orchestrator 2026-08-10) — **Ratify as intentional.**
The sacrificial bounded-repeat trade-chain already shipped on main (#637,
`22dfe7f3`) is authorized as designed, not an undocumented automation leak.

**Reasoning.** Max's 2026-08-10 ruling matches the prior 2026-07-21 witness
carte-blanche for autonomous trade + chain-seeking on disposable / sacrificial
accounts. It ratifies the mechanism **as shipped** and invents no new
authorization:

- `pass_count > 1` is `is_crawl_sacrificial`-only (`TradeChainRunner.start`
  raises `bounded_repeat_requires_sacrificial` otherwise).
- Default arm remains one pass (omit `--pass-count`).
- Multi-pass is explicit (`--pass-count` / `pass_count`).
- Caps: `DEFAULT_MAX_PASSES=10`, `PASSES_HARD_CEILING=50`.
- Before every re-arm, the X5 stop-loss floor and optional profit-target are
  re-checked; whichever of (pass-count, floor, profit_target) trips first
  stops.
- Same fingerprint only — no finder-initiated launch, no next-chain rotation.
- Do not widen to non-sacrificial / real player accounts without a new
  design ruling.

Item 8 of `DECISION-ADR-003-RESIDUAL-7-8` remains **Accepted — shipped**; this
entry is the canon-honesty follow-through, not a re-open of those scoping
questions.

**Refs:** orchestrator.md 2026-08-10T19:14:00Z / 2026-08-10T19:18:00Z ·
`workorders/WO-CANON-RATIFY-BOUNDED-REPEAT-TRADE-CHAIN.md` · PR #674 ·
`tw2002_aiclient/bounded_repeat_trade_chain_driver.py` ·
`canon/strategy/trade-loops.md` · ADR-003 (Folded).

## DECISION-SHIP-UPGRADE-TRADE-IN-ECONOMICS (2026-08-12)

**Status:** Accepted (hub GO 2026-08-12T04:18:34Z — batch-4 ACK greenlit this WO)

**Ruling.** Ship-upgrade `projected_payback` amortizes **net cash outlay**, not gross list
price, when trade-in credit is known:

`net_cash_outlay = max(0, candidate.list_price − trade_in_credit) + hold_fill_cost(extra_holds)`.

- `trade_in_credit` is **omit-until-known** (status key `upgrade_trade_in_credit` or an
  explicit pure-engine kwarg). Default / unknown = `0` — keeps the pre-existing pessimistic
  HOLD bias; does **not** assert that shipyards pay zero trade-in.
- **Never invent** a server-wide trade-in percentage. Live confirm-screen credit deltas remain
  a capture/driver follow-up; this decision only corrects the ROI math contract.
- Recommend-only / purchase-adapter HELD posture from `DECISION-PWO-107-SHIP-UPGRADE-DECISION-PORT`
  is unchanged.

**Refs:** `canon/strategy/ship-progression.md` § Trade-in ·
`tw2002_aiclient/ship_upgrade_decision.py` ·
`workorders/WO-CANON-DRAFT-SHIP-UPGRADE-TRADE-IN-ECONOMICS.md` ·
orchestrator.md 2026-08-12T04:18:34Z.

## PENDING-PLAYER-ROTATION-AUTO-SWITCH-CONSUMER (2026-08-12)

**Status:** Pending — Orchestrator review, needs Max (auth-adjacent, on the safety list)

**Finding.** `player_bank.advance_rotation()` / `tw players rotate` already produce a correct,
safety-reviewed `RotationDecision(name, reason)` for credential-bank multi-character rotation
(TW-31) — the decision math is done and the credential bank itself is metadata-only (no
cross-account transfer risk). But canon (`canon/surfaces/entry-and-profile-selection.md:410-417`)
states plainly the daemon-side consumer that would actually *act* on a driver decision
(auto-login / auto-switch) "remains a separate future wave" — nothing calls
`advance_rotation` from the daemon, cockpit, or any scheduled path today; it is CLI-only,
read-only-forever unless invoked by hand.

**Why this needs a ruling, not a WO.** Any consumer that would auto-login/auto-switch characters
touches the login automaton and control-lock — explicitly auth-adjacent per parent CLAUDE.md's
safety list. Two shapes are on the table: (a) a real auto-switch daemon consumer, or (b) a
passive cockpit/CLI notify-only surface ("X is due, rotate?") with no auto-login at all. (b) is
almost certainly buildable without a gate; (a) needs an explicit Max GO given the auth-adjacency.

**Refs:** `tw2002_aiclient/session/player_bank.py` · `tw2002_aiclient/players_cli.py` ·
`canon/surfaces/entry-and-profile-selection.md:410-417` · 6-lens aiclient audit, 2026-08-12
(build-and-unwired lens).

**Update 2026-08-14.** Option (b) shipped as `tw players rotate --check` (notify-only; exit 0
even when nobody is due; exit 2 on BankUnreadable) via WO-BUILD-ROTATION-NOTIFY-ONLY-SURFACE
(PR #706, `d7bd7f0`). Canon coverage for the flag landed in WO-CANON-DRAFT-PLAYERS-ROTATE-CHECK-FLAG
(PR #711, `ad8c0ac` — `cli-verbs.md` players row + `entry-and-profile-selection.md` rotation-driver
paragraph). Only option (a) — the auth-adjacent auto-switch daemon/cockpit consumer — remains
open and Max-gated. This entry stays Pending for (a); (b) is no longer an open menu item.

## PENDING-AI-TEACHER-LLM-BACKEND-WIRING (2026-08-12)

**Status:** Pending — Orchestrator review, needs Max (new external dependency + AI-dialogue,
doubly on the safety list)

**Finding.** The entire on-demand AI-teacher author path (`tw teach analyze`, cockpit Analyze
overlay, draft-and-approve gate) is tip-closed and correctly ethos-bound, but it can never
actually run: `AnalyzeBackend` is injectable in `tw2002_aiclient/ai_teacher.py` but the default
backend raises `no_backend_configured` — no real model client is wired. Canon
(`canon/engine/ai-teacher.md:169-179`) already names this: "a real model client is injectable
via AnalyzeBackend but not wired — new external dependency, still Max-gated."

**Why this needs a ruling.** Both "new external dependencies" and "AI-dialogue/ARIA-LLM" are
independently on parent CLAUDE.md's safety list — this finding is doubly gated. No DECISIONS.md
entry existed naming which model/provider to wire before this pass, so the fully-built plumbing
was at risk of staying permanently dead with no tracked ask. Needs Max to name a provider/model
(or explicitly decline to wire one for now).

**Refs:** `tw2002_aiclient/ai_teacher.py` · `canon/engine/ai-teacher.md:169-179` · 6-lens aiclient
audit, 2026-08-12 (build-and-unwired lens).

## PENDING-SHIP-UPGRADE-TOGGLE-MISLEADING-DEFAULT (2026-08-12)

**Status:** Pending — Orchestrator review, needs Max (UX mechanic choice among distinct options,
not a pure number)

**Finding.** `cockpit/teachband.py` (lines 120, 196, 224, 368) defaults the `S)hip Upgrade`
toggle chip to display `·ON` even though the toggle currently gates zero purchase behavior — no
ship-purchase send/confirm driver exists in tip. Canon (`canon/surfaces/mode-line-and-teach-
controls.md` § Policy-auto amendment) already documents this honestly as "gates nothing yet" —
code and doc agree in substance, this is not a hidden defect. But operationally the chip sits
beside `P)ort Trade` and `C)argo Hold Upgrade` toggles that DO gate real spend, with an operator
having no way to distinguish inert-vs-live from the chip alone.

**Options on the table:** (a) default `S` to `OFF` until the purchase path ships, or (b) keep
`ON` but visually distinguish inert-vs-live toggles (e.g. a dimmed/hatched state). Left as a
genuine design-taste call per the ratification-authority amendment (CLAUDE.local.md,
2026-08-10) rather than self-ruled, since it's a UX mechanic choice among distinct options, not a
faucet-rate/magnitude-style number.

**Refs:** `tw2002_aiclient/cockpit/teachband.py:120,196,224,368` · `canon/surfaces/mode-line-and-
teach-controls.md` § Policy-auto amendment · 6-lens aiclient audit, 2026-08-12 (code-vs-canon
lens).

## DECISION-PORT-FLOOR-TRADED-SINCE-PRIOR-ACCEPT-DARK (2026-08-15)

**Status:** Ruled (hub self-ruled 2026-08-15, logged `port-floor-traded-since-prior-accept-dark`
(Decided) in the Nebuspace decisions DB) — **accept-dark** for tip product capture. The either/or
("wire a `traded_since_prior` signal" vs "accept regrowth stays dark") is closed on the
accept-dark horn.

**Reasoning.** Product capture (`world_model._record_port_floor_observation` →
`port_floor_capture.record_port_write`) has no operator ledger of whether *this* profile traded the
port since the prior observation. Marking pairs `False` without that ledger would fabricate
trade-free windows and make `estimate_regrowth_rate` look live when it is not. Marking `True` would
silently drop every pair. Leaving the flag unknown yields `{}` from product JSONL — honest empty,
not a silent wiring gap. This sits under the existing analysis-only hold
(`DECISION-PORT-FLOOR-CAPTURE-HOLD-RATIONALE`): no ranking/coach consumer is owed a regrowth number
from this path. PR #715 documented the darkness; this ruling **decides** it rather than leaving the
queue either/or open. A future ledger-aware capture WO may set the flag; that is new scoped work,
not a reopen of this decision by default.

**Refs:** hub ruling `port-floor-traded-since-prior-accept-dark` (Nebuspace decisions DB, Decided
2026-08-15) · `tw2002_aiclient/port_floor_capture.py` · `tw2002_aiclient/world_model.py`
(`_record_port_floor_observation`) · `canon/strategy/port-economics.md` § port_floor_capture ·
`DECISION-PORT-FLOOR-CAPTURE-HOLD-RATIONALE` · WO-ESCALATE-PORT-FLOOR-TRADED-SINCE-PRIOR-UNREACHABLE.
