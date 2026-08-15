# WO-AICLIENT-FIX-TRADEIN-CREDIT-UNREACHABLE-EVIDENCE

**Priority:** MED  
**Claimed-by:** impl-aiclient-h1

## Goal

Trade-in credit stays at pessimistic `0` when evidence is unreachable; make that
gap visible via `trade_in_unverifiable` (distinct from plain omit-until-known).

## Changes

- `evaluate_candidate` / `choose_upgrade`: `trade_in_unverifiable=` kwarg → flag
- `upgrade_decision_from_status`: reads `upgrade_trade_in_unverifiable: true`
- Canon `ship-progression.md` documents the flag + status key
- Math unchanged (still credit 0 until observed)

## Accept

- [x] Flag present when unverifiable + credit ≤ 0
- [x] Flag absent for plain omit or when credit observed
- [x] Payback identical to omit-until-known when unverifiable
- live-prove: n/a (recommend-only decision engine; no send path)

## Proof

```bash
.venv/bin/python -m pytest tests/test_ship_upgrade_decision.py -q -n0 -k trade_in
```
