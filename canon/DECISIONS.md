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

### PENDING-HUD-CARGO-BREAKDOWN — CARGO shows empty/total (+ holdings next) (2026-08-01)

**Edge:** Change — `trainer-cockpit.md` said CARGO is **empty holds only**; Max (2026-08-01) asked the right HUD to explain **what is in cargo holds**. Bare `CARGO 50` reads as contents.

**Kernel (build now · Max product ask = GO for display honesty):**
1. CARGO paints **empty and total** when ship-info `Total Holds : N - Empty=M` is known (filled = N−M is implied, not a third invented claim).
2. Port-commerce empty-only lines still update empty; do not invent total from port **market** commodity rows.
3. Per-commodity Ore/Org/Equ sticky holdings = follow-on WO (`WO-HUD-CARGO-HOLDINGS`), fed by trade buy/sell and/or future ship-info lines — still never from market rows.

**Status:** Pending formal RESOLVED stamp; product kernel executing under Max ask.

---


## RESOLVED

<!-- Items with a human decision on record. Waiting for ADR drafting or already captured. -->

### RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731 — trainer Play chrome + App-armed default (Max 2026-07-31)

**Edge:** Conflict + Change — calm strip / seat+arm / CONN / panic / money-path confirm-not-auto vs Max trainer model.

**Ruling (Max, session 2026-07-31 — “Proceed”):**

1. **Seat:** One chip with Mode key — `^A)APP-ARMED` / `^A)MANUAL-HUMAN`. Merge APP+ARM. Halt = leave App → Manual (STOP/PANIC redundant as operator controls).
2. **Calm keys:** `E)xplore` · `P)ort Trade·ON/OFF` (default ON) · `L)oops` · `T)rade Loop Chain` · `C)argo Hold Upgrade·ON/OFF` (default ON) · `S)hip Upgrade·ON/OFF` (default ON). Retire A/R/T/V/U/H/O/Panic from calm band.
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

### OPEN-002 — Commit the remaining untracked `canon/**` / `workorders/**` bundles — CLOSED

**Filed:** 2026-07-24
**Filed by:** Monk (via orchestrator WO-ADR-001-ACCEPT)
**Edge type:** Gap

**Question:**
The `canon/` tree (and `workorders/**`) has a substantial body of untracked bundles beyond the
ADR-001 fold-in touched here. Committing the remaining untracked `canon/**`/`workorders/**` content
needs a deliberate Max GO before it lands in git — do not `git add` wholesale until then.

**Why it matters:**
A blanket `git add -A`/`git add canon/**` would sweep in content that hasn't had an explicit
commit decision, mixing unrelated bundles into one commit and losing the ability to review them
individually.

**Resolved (2026-07-24) — CLOSED.** Hub autonomously GO'd the bundle commits (already-authored docs,
not a new design). `canon/**` committed in `e2fda40` — the full 37-concept bundle is tracked, 0
untracked. Remaining `workorders/**` (README · ULTRACODE inventory · legacy WO-00…17 · remaining
WO-P1) committed via WO-WORKORDERS-BUNDLE-COMMIT (explicit paths only, never `git add -A`; Cursor
seat after CC reassignment). Remaining public-bound hygiene owed **before any push**: relativize
the absolute `/Users/…` Proof-path `cd`/`.venv` lines across `CLAUDE.md` + `workorders/**` (banked
LOW — the leak-gate-precedes-push discipline covers it).

### OPEN-001 — One package tree vs. the Phase-0 two-top-level-package scaffold — RESOLVED/CLOSED

**Filed:** 2026-07-23
**Filed by:** Monk (via orchestrator WO-ADR-001-ONE-TREE)
**Edge type:** Change

**Question:**
WO-P0-003 stood up two sibling top-level packages (`tw2002_aiclient/` product TUI + `twclient/`
daemon-core) reading the session-engine's two-*process* split as a two-*package* split. Max ruled
this wrong for greenfield: the codebase should live under one importable tree
(`tw2002_aiclient/`, with the daemon-core relocated to `tw2002_aiclient/session/`), while the
2–3-process runtime split (`twd` / `tw` / the TUI app) stays exactly as canon already specifies.
Is this ruling ready to accept as ADR-001, and — separately — does the aiclient app's on-exit
"stop the daemon too?" confirm popup default to **Yes** or **No**?

**Why it matters:**
Every future daemon-core WO (WO-P2-020 through WO-P2-028 and beyond) currently targets `twclient/*`
import paths. Left unresolved, new work keeps building against the wrong packaging shape, growing
the relocation's blast radius the longer Accept is deferred.

**Options considered:**
A) Accept ADR-001 as drafted (one tree, `session/` subpackage name, exit-popup default TBD) and
   schedule the relocate WO immediately after Accept.
B) Accept the one-tree decision but rename the subpackage `engine/` instead of `session/`.
C) Leave the two-package scaffold as-is (rejected by Max's ruling; recorded here only as the
   status-quo alternative).

**Unambiguous kernel built while waiting:**
This DECISION, ADR-001 (Proposed, not self-Accepted), and the canon fold in
`canon/architecture/session-engine.md`, `canon/surfaces/trainer-cockpit.md`, and
`canon/surfaces/entry-and-profile-selection.md` — all citing ADR-001 as "Proposed; pending Accept."
No product code was written and no package was relocated; that work is explicitly deferred to a
follow-on WO listed in ADR-001's Consequences, gated on Accept.

**Resolved:**
Max Accepted ADR-001 2026-07-24; exit-popup default = **No** (leave daemon running); subpackage =
**`session/`** (Option A, not B). Canon fold-in (`session-engine.md`, `trainer-cockpit.md`,
`entry-and-profile-selection.md`, `CLAUDE.md`) updated to cite ADR-001 as Accepted and to state the
exit-popup default. Physical package relocation remains explicitly deferred to the follow-on WO
listed in ADR-001's Consequences — not executed by this closure.

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

### C — Secrets surfaces (`repr(UnicodeDecodeError)` / `get_password` / stuck-login wire)

**GO rehab:** decode/permission failures → typed redacted errors; **never** put secret or undecoded secret-adjacent bytes into `repr()`, exception strings, CLI JSON, or logs. `get_password` failure → `None` or typed error without payload leak. Stuck-login RX-on-wire stays redacted. Orthogonal to ensure-JSON MT-07 (already separate).

### D — Settle default ownership (prompt settle)

**Settle-detection owns readiness** ("is the stream settled / safe to act"). **Screen-understanding owns identity** ("what screen is this"). Drive verbs (`do`) take settle-detection's prompt-line + `rx_count` / freshness discipline as default `match_scope`; classify vocab does **not** set settle readiness. Closes the open note under P-SETTLE-LINE.

### E — Catalog public names + `twgs.exiled.org`

1. **Keep** third-party BBS directory display names (including Firstname-Lastname shapes) as published catalog provenance — not a privacy scrub target in this public-game-directory sense.
2. **Keep** `twgs.exiled.org:2002` with honest `archive_seed` / known-exception status (do not drop). Operator may still use it; catalog must not lie that it was absent from greenfield when it was not.

### F — Throwaway-worktree lifecycle (Proposed → Accepted with CC amendments)

Accepted: owner removes on Accept/abandon; `preserve/<wo-id>` if tip ∉ origin; hub mass-prune only after `🧹 PRUNE-INTENT` + seat ACK; **never remove a LOCKED worktree** (lock carries PID; `kill -0` detects stale); soft ceiling **12 is a reporting trigger**, not a removal trigger (CC amendment B). Hub may lift 🧹 PRUNE PAUSED after seats ACK this Accept note.

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

