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

<!-- (empty — OPEN-003 formally CLOSED 2026-07-25) -->

---

## RESOLVED

<!-- Items with a human decision on record. Waiting for ADR drafting or already captured. -->

<!-- (empty — nothing resolved yet) -->

---

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
