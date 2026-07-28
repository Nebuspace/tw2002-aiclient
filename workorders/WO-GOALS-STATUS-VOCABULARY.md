# WO-GOALS-STATUS-VOCABULARY — T0 guard + T1 client overlay

**Status:** OPEN EXECUTE · HIGH · Claude Code preferred  
**Posted:** 2026-07-28T13:45Z · hub (CC scope 13:42Z · ruling 13:43Z)  
**Depends:** #162 chain scalars precedent (`ChainScalars` client overlay)

## Goal

Close the honest-but-uninformative GOALS/status gap: document starved `status` keys, prevent silent regrowth, then wire **T1** client-side world-model fields without daemon/protocol changes.

## T0 — guard (commit 1, before any wiring)

- Pin: **exact-set equality** between computed `starved = consumed − emitted` and an **explicit allowlist** (must fail if new starved key OR stale listed key after supply).
- Scanner must resolve **named constant** subscripts (e.g. `HOPS_KEY`) and **exclude label-table** false positives (`_LABELS`, `_FIELD_LABELS`).
- Allowlist entries include **WHY** + tranche (T2/T3/T4) per field; `liveness.py` deliberate pending = documented, not defect.

## T1 — client overlay (commit 2, after T0 green on 18-starved tree)

Wire from world model (no daemon): `known_sectors`, `galaxy_size`, `formations_count`, `stardock_found`, `stardock_sectors`.

- **`stardock_found` / `stardock_sectors`:** `stardock_found` is written only when the world model has positively established the answer. `False` = searched-and-confirmed-absent; “have not looked” = **absent**, never `False` (default `False` would gate `ship_prices`/`hold_price` to ⊘ and hide good data). Tri-state pinned with ⊘ gate asserted for all three states (CC 13:44:31Z table).
- Delete **exactly 5** allowlist entries when wired; guard must go red on wrong deletion count.

## Out of scope (banked)

- T2 `credits` (daemon / DEPLOY-WINDOW) · T3 screen parsing · T4 whole-panel payloads

## Accept

1. T0 green on pre-T1 tree with full 18-entry allowlist; falsification pins for both scan traps.
2. T1 green; 5 fields supplied; allowlist shrinks by 5 with exact-set still green.
3. Suite + STATUS; two commits reported separately; live-prove `n/a`.

## Refs

- CC 13:42–13:43Z coord · hub 13:43:30Z ruling
