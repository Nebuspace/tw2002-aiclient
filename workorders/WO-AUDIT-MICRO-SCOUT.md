# WO-AUDIT-MICRO-SCOUT — Enrich DRAFT micro WOs with confirmed file:line citations

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-25 · tip **`78f4bb5`** (Cursor)
> Type: docs/inventory · Priority: P1 · Lens: L5 doc/canon gaps
> Refs: `WO-AUDIT-RECONNECT-EXCEPT-COMMENT.md` · `WO-AUDIT-CLI-KEYS-IGNORE-RETURN.md`

## Goal
Enrich DRAFT micro audit WOs with confirmed `file:line` citations + one-sentence Accept polish (no inventing Max keys). Specifically: `WO-AUDIT-RECONNECT-EXCEPT-COMMENT.md` — locate reconnect broad-except; pin path:line. `WO-AUDIT-CLI-KEYS-IGNORE-RETURN.md` — locate `cli --keys` ignore-return; pin path:line. Optional: note on `WO-AUDIT-SAFE-WIDTH-DOCSTRING.md` that tip awaits origin.

## Scope
- `workorders/WO-AUDIT-RECONNECT-EXCEPT-COMMENT.md` — add path:line from origin
- `workorders/WO-AUDIT-CLI-KEYS-IGNORE-RETURN.md` — add path:line from origin
- Optional: `WO-AUDIT-SAFE-WIDTH-DOCSTRING.md` tip-honesty note

## Constraints
- Docs only; no `.py` changes
- No inventing Max keys; no inventing Accept criteria
- Origin = `01bac96` at time of HANDOFF

## Accept
1. Both DRAFTs cite real path:line from current `origin/main`
2. Diff reviewable (Scout diff only)

## Proof
Diff review. Hub Accept `78f4bb5` + Push GO @ 07:01:25Z.

## Refs
hub HANDOFF @ 06:59:07Z · orbit WO-AUDIT-RECONNECT-EXCEPT-COMMENT + WO-AUDIT-CLI-KEYS-IGNORE-RETURN
