# WO-AUDIT-CANON-DRAFT-AI-PILOT-RETIREMENT-STALE

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** MED
**Depends-on:** none
**Gated:** no — canon honesty only

## Goal

Three canon files still assert `MODE_AI_PILOT` as a live unresolved tip divergence. Tip
`tw2002_aiclient/session/control_lock.py` already has only `{app, human, spectate}`. Mark
retirement DONE; keep do-not-revive in findings.

## Scope

- `canon/architecture/control-and-escalation.md`
- `canon/architecture/session-engine.md` (same stale claim, found while verifying)
- `canon/doctrine/action-safety-guards.md`
- `canon/surfaces/spectate-and-attach.md`
- `canon/findings.md` §1
- This WO file

## Accept

1. Cited sections no longer claim MODE_AI_PILOT is a live tip-code divergence.
2. Evidence pointer to tip `session/control_lock.py` modes `{app, human, spectate}`.
3. findings.md keeps ai_pilot as do-not-revive / historical, not an open tip bug.
4. live-prove: `n/a` (docs only).

## Proof

Diff review + `rg MODE_AI_PILOT` on tip control_lock (zero) vs updated canon prose. STATUS with SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-AI-PILOT-RETIREMENT-STALE`
- `tw2002_aiclient/session/control_lock.py:151-160`
