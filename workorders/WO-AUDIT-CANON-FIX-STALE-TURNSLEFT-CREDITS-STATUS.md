# WO-AUDIT-CANON-FIX-STALE-TURNSLEFT-CREDITS-STATUS

**Status:** CLAIMED by `impl-aiclient-cursor` (idle-kick resume after #377 hub-merge)
**Priority:** MED
**Depends-on:** none (WO-STATUS-CREDITS + WO-HUD-STATUS-BRIDGE already shipped)
**Gated:** no — canon honesty only

## Goal

Flip `canon/engine/priority-engine.md` row #1 off **Starved**: top-level `turns_left` /
`credits` are produced by `protocol._status_response` and consumed by GOALS. Narrow residual
to omit-until-read + FOCUS not yet weight-gating on unmet #1.

## Scope

- `canon/engine/priority-engine.md` (row #1 + audit note)
- This WO file

## Out of scope

- Code changes to FOCUS weight-100 gating (separate build WO if desired)
- Rows #3–#13 honesty (except leaving them untouched)

## Accept

1. Row #1 Status is no longer "Starved" with the false "no producer" claim.
2. Residual gaps (omit-until-read; FOCUS #1 overlay) named honestly.
3. live-prove: `n/a` (docs only).

## Proof

Diff review of the status cell; STATUS with SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-FIX-STALE-TURNSLEFT-CREDITS-STATUS`
- `tw2002_aiclient/session/protocol.py` ~402–424
- `tw2002_aiclient/cockpit/goals.py` ~200–212
