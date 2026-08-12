# WO-CANON-DRAFT-CHAIN-STATUS-NO-COVERAGE

**Status:** DONE · tip coaching-engine.md cites chain_status.py ChainScalars LIVE
**Priority:** MED  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-36 / queue-aiclient.md

## Goal

Document shipped `chain_status.py` (cached `chain_hops`/`chain_unit` producer, honest-absence
semantics, why-not-recompute) in coaching-engine.md. Module previously had zero canon name hits.

## Tip-verify (2026-08-06 @ main `dda7122`)

| Check | Result |
|---|---|
| Module | `chain_status.py` ~500 lines LIVE |
| Consumers | goals.py, decisions.py, focus_status.py, screens/app PlayShell |
| Prior canon | coaching-engine cited `chain_hops`/`chain_unit` as inputs; never named the producer module |

## Diff

- New bullet under coaching-engine tip-status section
- Code modules list adds `chain_status.py`

## Accept

- [ ] Cache-not-recompute + honest absence + LIVE producer named
- [ ] No product code change

## live-prove

`n/a` — canon staging of shipped status helpers.
