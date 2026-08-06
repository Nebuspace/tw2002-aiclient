# DECISIONS archive — closed entries

Append-only home for **CLOSED** DECISIONS.md threads whose durable ruling already lives in an
ADR or tip canon. The live `DECISIONS.md` keeps a one-line pointer so the open-questions workspace
stays scannable.

---

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
the absolute operator-home Proof-path `cd`/`.venv` lines across `CLAUDE.md` + `workorders/**` (banked
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
