# WO-AUDIT-CANON-DRAFT-AUTONOMY-POLICY-COVERAGE

**Status:** CLAIMED by `impl-aiclient-cursor` (`📋 CLAIM` 2026-08-04T18:58:30Z)
**Priority:** MED
**Depends-on:** none
**Gated:** no

## Goal

Give `autonomy_policy.py` a canon home: FOCUS → confirm offer selection
(`choose_offer` / `AutonomyOffer`), not a second EV picker.

## Approach

Fold into existing [priority-engine](../canon/engine/priority-engine.md) (Layer 2
FOCUS sibling section) rather than a new OKF concept — avoids the create/rename
gate; queue Accept allowed fold-in.

## Scope

- `canon/engine/priority-engine.md` — Owns row + new section + citations
- This WO file

## Accept

1. Canon names `choose_offer` / offer kinds / StarDock early-game bias / idle fail-closed.
2. Explicitly states the selector does not live-send.
3. Cross-links consumers (`O` confirm, App-armed auto-fire constraints).
4. live-prove: `n/a` (docs-only).

## Proof

`rg autonomy_policy|choose_offer canon/engine/priority-engine.md` + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-AUTONOMY-POLICY-COVERAGE`
- `tw2002_aiclient/autonomy_policy.py`
