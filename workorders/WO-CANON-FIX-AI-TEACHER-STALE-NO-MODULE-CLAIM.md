# WO-CANON-FIX-AI-TEACHER-STALE-NO-MODULE-CLAIM

**Status:** DONE · PR #662 · tip ai-teacher.md names write_draft / tw teach analyze
**Seat:** `impl-aiclient-cursor`
**Depends:** `main` ≥ `0fa9c855` (#661 MERGED)
**Refs:** cycle-49 audit · `canon/engine/ai-teacher.md` Code divergence ·
`tw2002_aiclient/ai_teacher.py` · `teach_cli.py` · cockpit Analyze wiring (#515, #564)

## Why

`canon/engine/ai-teacher.md` still claimed **"There is no AI-teacher module"** and
described Screen-Analyze LLM plumbing as unbuilt. Tip has shipped the author-only,
ethos-bound `write_draft` path, `tw teach analyze`, and cockpit Analyze-close wiring
for weeks. Real LLM backend remains deferred (new-dep Max-gate).

## Goal

Docs tip-true only: rewrite the stale "no module" bullet; keep correctly-closed
`MODE_AI_PILOT` and ledger sender-enum notes.

## Scope

1. `canon/engine/ai-teacher.md` — Code divergence intro + first bullet.
2. This WO file.

## Out of scope

- Wiring a real LLM SDK / `AnalyzeBackend` product default (new external dependency).
- Changing `ai_teacher.py` / teach CLI / cockpit behavior.

## Accept

1. Canon no longer claims "there is no AI-teacher module."
2. Canon names shipped surfaces + deferred backend explicitly.
3. Other closed divergence bullets preserved.

## Proof

- Diff review of `canon/engine/ai-teacher.md` only (+ this WO).
- `live-prove: n/a` (docs-only).
