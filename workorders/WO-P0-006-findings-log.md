# WO-P0-006 — Findings log (+ archive reference index)

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 0 · **Type:** docs-finding · **Depends:** WO-P0-004
**Canon:** north-star conventions (`canon/architecture/north-star.md`), plus the divergence sections
of `canon/architecture/session-engine.md`, `canon/architecture/control-and-escalation.md`,
`canon/engine/priority-engine.md`, `canon/engine/auto-haggle.md`

**Goal:** Centralize the recorded canon-vs-code divergences into one DOCS-WIN findings file at the
new greenfield root, and separately index what still lives under `archive/` as port-source (this WO
folds the former PWO-000 archive-inventory step into itself rather than opening it as its own file).

**Scope:** New `canon/findings.md` (or `workorders/FINDINGS.md` if `knowledge/` is not yet
scaffolded — pick one and note the choice in the file itself). No canon edit, no code.

**Accept:**
- The findings file records, at minimum, these four documented divergences with their canon source
  citation:
  1. `MODE_AI_PILOT` as a live-drive control-lock mode (no canon equivalent as a drive mode) —
     `canon/architecture/control-and-escalation.md` Code Divergence.
  2. The per-cycle EV action-picker shape (`autopilot.select()` scoring `run_chain`/`upgrade`/
     `explore` from scratch every tick) versus the reborn taught-behavior run-loop that stops on
     the unknown — `canon/engine/priority-engine.md` Code Divergence.
  3. The `{ai, trainer, human}` ledger actor enum (default `"ai"`) versus the reborn `{app, human}`
     live-sender invariant — `canon/architecture/session-engine.md` and
     `canon/engine/trace-ledger.md` Code Divergence sections.
  4. The verified 78-turn-autopilot money-path misfire — `canon/engine/auto-haggle.md` Code
     Divergence (the founding auto-haggle finding).
- A short **REFERENCE-ONLY** section maps what lives under `archive/pre-rebirth-2026-07-23/` as
  port-source: at minimum the top-level dirs (`code/`, and any `config/`/`runtime/` siblings if
  present) with a one-line note that nothing under `archive/` is imported by the greenfield tree.
- The file states plainly it edits no code and is documentation-only.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
ls archive/pre-rebirth-2026-07-23/                       # confirms the archive-reference section is accurate
grep -c "MODE_AI_PILOT\|per-cycle EV\|actor.*ai.*trainer.*human\|78-turn" canon/findings.md
# expect 4 matches, one per finding
```
