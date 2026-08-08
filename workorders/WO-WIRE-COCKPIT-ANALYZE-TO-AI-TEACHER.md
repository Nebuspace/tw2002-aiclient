# WO-WIRE-COCKPIT-ANALYZE-TO-AI-TEACHER

**Status:** READY · gated: no
**Posted:** 2026-08-08 · impl-aiclient-cursor self-select (hub ACK+HANDOFF 12:59Z)

## Goal
Play cockpit `analyze_close` scaffolds a local draft via `draft_approve.create_analyze_draft` and never calls `ai_teacher.analyze_escalation`. Canon Screen Analyze (A) should invoke the retrospective AI teacher. Wire the call site; keep scaffold UX when no LLM backend is configured.

## Scope
- `tw2002_aiclient/ai_teacher.py` — cockpit-facing complete helper
- `tw2002_aiclient/app.py` — `analyze_close` action
- tests proving teacher path + no-backend fallback
- this WO file

## Constraints
- No new external LLM dependency (backend stays injectable; default `no_backend_configured`).
- AI never sends keystrokes. Teacher output is draft-only / decline-only.
- Do not weaken route-hazard or other safety gates.
- Preserve current y/N scaffold approve flow when backend is not configured.

## Accept
1. `analyze_close` routes through an `ai_teacher` helper that either runs `analyze_escalation` or falls back to `create_analyze_draft`.
2. Injected valid backend → inert draft on disk (`approved: False`); no scaffold identity gate.
3. Default / missing backend → scaffold path unchanged (pending draft + draft-approve gate).
4. Ethos decline → status reason, no draft file, stub_store untouched.
5. Structural: no live-send on the new path.

## Proof
Targeted pytest for the wire + related ai_teacher/cockpit pins. live-prove: n/a (offline wire; no live TWGS surface).

## Refs
- `canon/engine/ai-teacher.md` (Screen Analyze / on-demand)
- Gap: `app.py` `analyze_close` → `create_analyze_draft` only; CLI `tw teach analyze` already uses `ai_teacher`
