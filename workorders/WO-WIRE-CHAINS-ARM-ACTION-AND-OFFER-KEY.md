# WO-WIRE-CHAINS-ARM-ACTION-AND-OFFER-KEY

## Goal
Wire dead `resolve_chains_offer_key` / `compose_arm_action` into the live L→arm→T path
without reintroducing a y-gate on Enter (RESOLVED Trade Loop mode-split).

## Scope
- `tw2002_aiclient/screens.py` — L via `resolve_chains_offer_key`
- `tw2002_aiclient/app.py` — taught Enter status via `compose_arm_action`; store `steps`
- tests + this WO file

## Accept
1. `screens.py` calls `cockpit_chains.resolve_chains_offer_key` (not bare `ord("l")`).
2. Taught Enter status uses `compose_arm_action` disclosure; still no y-gate on Enter.
3. `L` Enter `T` with Port Trade·ON still starts taught/discovered runners.
4. Focused chains arm tests green.

## Proof
- pytest `tests/test_play_chains_arm.py` `tests/test_play_chains_discovered.py` `tests/test_cockpit_chains.py`
- live-prove: offline key/status wire — hub may still want diversity on play path; seat notes honesty

## Out of scope
Reintroducing armconfirm y-gate on taught T (would fight mode-split pins) · discovered confirm rewrite
