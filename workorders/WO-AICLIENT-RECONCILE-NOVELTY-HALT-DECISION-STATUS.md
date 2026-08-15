# WO-AICLIENT-RECONCILE-NOVELTY-HALT-DECISION-STATUS

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1

## Goal

Reconcile DECISIONS.md "open Max-ruling" vs exploration-policy "already
closed/do-not-revive" on explore-baseline-EV vs novelty-halt — tip-check
code first; do not silently pick a side.

## Tip-check

| Fact | Evidence |
|---|---|
| No tip EV never-idle driver | no `tw2002_aiclient/autopilot.py` |
| `EXPLORE_BASELINE_EV` | only `focus_status.py` (suggestion `ev_per_turn`) |
| Novelty-halt | `action_safety.py` `guard_id="novelty_halt"` |

**Stale:** carte-blanche Left Pending bullet grouping the three escalate WOs.  
**Accurate:** exploration-policy / action-safety-guards tip-closed framing.

## Changes

- DECISIONS: tip-closed entry + remove stale Left Pending bullet
- app-autopilot-model: drop "still gated" wording for the driver half
- exploration-policy: point at the tip-closed DECISIONS entry

## Accept

- [x] Both sides cited; code evidence table in DECISIONS
- [x] Stale Pending removed; tip-closed recorded
- live-prove: **n/a** (canon / decisions log only)

## Proof

```bash
test ! -f tw2002_aiclient/autopilot.py
rg -n 'EXPLORE_BASELINE_EV' tw2002_aiclient/
rg -n 'tip-closed — EXPLORE_BASELINE' canon/DECISIONS.md
```
