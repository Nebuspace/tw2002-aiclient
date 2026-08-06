# WO-CANON-ROLLUP-ADR-002-MODE-CHORD

**Status:** OPEN (in PR)  
**Priority:** LOW  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-39 / queue-aiclient.md (Cycle-42 noted as duplicate of this row)

## Goal

Fold ADR-002's Mode rule into `control-and-escalation.md` as the single durable prose home; keep ADR-002 as the decision/pointer record.

## Tip-verify (2026-08-06 @ main `603543d`)

| Check | Result |
|---|---|
| `control-and-escalation.md` § The Mode Switch | Already states Ctrl-A Mode, no printable Mode, attached `M` = Move, Spectate ≠ Mode, cites ADR-002 |
| Sibling surfaces | Already cite ADR-002 / Ctrl-A LIVE (mode-line, spectate-and-attach, trainer-cockpit, visual-language) |
| ADR-002 body | Decision + Consequences still accurate; Consequences listed "six folded concepts" without naming the prose home |

## Diff

- ADR-002 Consequences: name **canonical prose home** → control-and-escalation § Mode Switch; siblings cite ADR as pointer (no re-litigation).
- No edits to the six surface docs (already tip-honest).

## Accept

- [ ] ADR-002 Consequences points at control-and-escalation § Mode Switch
- [ ] Decision section unchanged (Ctrl-A / M=Move / Spectate≠Mode)
- [ ] No product code change

## Proof

Docs-only. Spot-check: open ADR-002 + control-and-escalation § Mode Switch.

## live-prove

`n/a` — ADR rollup / docs consolidation.
