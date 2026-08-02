# WO-FORMATIONS-CATALOG-PORT — Port formations catalogue into tw2002_aiclient

**Status:** OPEN · EXECUTE · HIGH · seat `impl-aiclient-cursor` only  
**Posted:** 2026-07-28T04:41Z · **Re-scoped:** 2026-08-02T03:10Z (hub · after CC misroute STOP)  
**Branch:** `wo/FORMATIONS-CATALOG-PORT` · PR #317  
**Zone:** `tw2002-aiclient` only — never Sectorwars  
**Refs:** ADR-001 deleted twclient · #142 catalog_provider seam · `canon/strategy/special-formations.md` · #247 E-cycle 2-wide

## Goal

Port a real formations catalogue API into `tw2002_aiclient` (or deliberate product decline). Plug it into `plan_find_formations(..., catalog_provider=...)` **and** a live product call path. Then rehab/collect formations tests.

## Hub rulings (2026-08-02) — do not freelance past these

1. **Call site (premise break):** `plan_find_formations` has **zero** product callers today (def + tests + docstring only). Accept requires adding a **real product call path**, not only passing `catalog_provider` into a dead function. Prefer wiring via explore / `warp_target_for_intent` formations intent (`explore.py` already notes formations waits on this WO). **Do not** widen Play's E-cycle beyond the #247 "cycle stays 2-wide" ruling — formations is a **separate** armable intent/path, not a third E-cycle slot.
2. **PR #152** MERGED is **WO-bank only** (`workorders/WO-FORMATIONS-CATALOG-PORT.md`) — not a product port. Build the port for real.
3. **`genesis_count`:** either add a consumer in `decisions.py` (same pattern as `dead_end_count`) **or** explicitly park the field in STATUS — no half-wired producer.
4. **`STARVED_ALLOWLIST`** in `tests/test_status_vocabulary_guard.py`: delete `formations_count` / `formations_panel` blocked entries in the **same** change (guard uses exact-set equality).
5. **Counts:** `formations_count` = number of items shown in the formations panel; `genesis_count` = count of genesis-kind candidates only (may equal if panel is genesis-only). Document in code/comments.
6. **Archive:** `archive/` may be absent from clean worktrees. Genesis-safety attested by `canon/strategy/special-formations.md` (LOCATE / CATALOG / RECOMMEND only — no Genesis/claim action). Canon-attested is Accept-sufficient; byte-verify archive if present.
7. **Seat / zone:** `impl-aiclient-cursor` · `tw2002-aiclient`. No Sectorwars paths.

## Accept

1. In-tree provider (or Max/hub-ruled decline + Formations affordance honesty).
2. Product call path reaches the provider (ruling 1).
3. Tests exercise provider + unavailable path; no `twclient`.
4. Rulings 3–5 satisfied or explicitly parked with STATUS reason.
5. Suite green + STATUS; live-prove per money-path / explore-adjacent rules (diversity when arming — Max sacrificial GO if turn-spending; safe transport half = hub GO).

## Constraints

No stub that only greens imports. Money-path adjacent if it drives explore. Explicit paths — never `git add -A`.

## Proof

```bash
# suite
# + STATUS with call-site path, allowlist diff, genesis_count disposition
```
