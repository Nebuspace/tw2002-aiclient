# WO-GOALS-STATUS-VOCABULARY — T0 guard + T1 client overlay

**Status:** DONE · origin `a8e18ed` (#164) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-28T13:45Z · hub (CC scope 13:42Z · ruling 13:43Z)  
**Depends:** #162 chain scalars precedent (`ChainScalars` client overlay)

## Goal

Close the honest-but-uninformative GOALS/status gap: document starved `status` keys, prevent silent regrowth, then wire **T1** client-side world-model fields without daemon/protocol changes.

## T0 — guard (commit 1, before any wiring)

- Pin: **exact-set equality** between computed `starved = consumed − emitted` and an **explicit allowlist** (must fail if new starved key OR stale listed key after supply).
- Scanner must resolve **named constant** subscripts (e.g. `HOPS_KEY`) and **exclude label-table** false positives (`_LABELS`, `_FIELD_LABELS`).
- Allowlist entries include **WHY** + tranche (T2/T3/T4) per field; `liveness.py` deliberate pending = documented, not defect.

## T1 — client overlay (commit 2, after T0 green on 18-starved tree)

Wire **`known_sectors` only** via **`WorldStats` cache** (same `wrap` seam as `ChainScalars`): **zero world-model reads on `status_provider()` draw path** — refresh at chains-popup (and explore-tick only on existing WM read paths).

**Re-tranche (stay on allowlist with evidenced WHY — CC 14:04:20Z):**
- `galaxy_size` → **T3** (no producer; `state_parser` forbids inventing)
- `formations_count` → **TW-16** — see `WO-FORMATIONS-CATALOG-PORT` (catalogue seam unimplemented)
- `stardock_found` / `stardock_sectors` → blocked until **`WO-WM-LANDMARKS-WRITE`** (WM never writes `landmarks[]`)

Delete **exactly 1** allowlist entry on T1 commit (`known_sectors`).

## Out of scope (banked)

- T2 `credits` (daemon / DEPLOY-WINDOW) · T3 screen parsing · T4 whole-panel payloads

## Accept

1. T0 green on pre-T1 tree with full 18-entry allowlist; falsification pins for both scan traps.
2. T1 green; `known_sectors` wired; allowlist shrinks by **1**; four fields re-tranched with reasons.
3. Suite + STATUS; two commits reported separately; live-prove `n/a`.

## Refs

- CC 13:42–13:43Z coord · hub 13:43:30Z ruling
