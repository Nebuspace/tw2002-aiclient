# WO-AUDIT-ULTRACODE-066-071-HONESTY — Inventory tip-truth for PWO-066…071

> Status: **DONE** 2026-08-03 · hub-flagged on #334 Accept · self-pick
> Refs: `ULTRACODE-WO-INVENTORY.md` · `WO-P5-066.md`…`071.md` · #334 Accept note

## Goal
Align ULTRACODE Phase-5 inventory rows (and the PREP banner that still says **066 STAGED**) with the WO files that already stamp **DONE**.

## Scope
- `workorders/ULTRACODE-WO-INVENTORY.md` — PWO-066…071 status cells
- `workorders/WO-P5-060-072-mode-teach-PREP.md` — header STAGED lie
- This WO file

## Constraints
- Docs only — no product code
- Cite WO tip SHAs where the WO files already record them; 066 paper-close cites its WO file

## Accept
Re-grep: no open `PWO-066 | … **STAGED**` or `PWO-071 | … PREP` rows; PREP header no longer claims **066 STAGED**.

## Proof
`rg` on inventory + PREP header.
