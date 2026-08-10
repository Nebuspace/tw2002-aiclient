# WO-BUILD-CHAIN-LONGEVITY-RANK-WIRE

**Status:** OPEN → this PR  
**Priority:** MED  
**gated:** no  
**schema:** n/a  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `f80715ab` (#648) · `WO-BUILD-CHAIN-DEPLETION-PREDICTOR` (#567)

## Goal

Give `rank_chains_by_longevity` a real product caller. Canon
(`port-economics.md` § Route-longevity) already claims tip ranks longevity via
that helper; tip only exercised it in unit tests while `chain_search.recompute`
offered `RANK_HOPS` / `RANK_YIELD` only — unused-code tip_check on the symbol.

## Verify-first (2026-08-10 @ `origin/main` `f80715ab`)

- `chains.rank_chains_by_longevity` / `chain_depletion.rank_chains_by_longevity`
  exist; product callers: **0** (`git grep` → tests only).
- Depletion STOP + status signals are already wired (`trade_driver` /
  `chain_status`); ranking half was the residual Accept gap.
- Skipped tip-closed READY ghosts: PORT-ECONOMICS-LEDGER (#648), MENU-MAP
  (#647), TRADE-DRIVER (#646), FRAMES (#642/#645), TEST-CATALOG (#644), prior
  tip-true list. Skipped WO-FIX-COORD-MONITOR (sectorwars-cursor).

## Scope

- `tw2002_aiclient/chain_search.py` — `RANK_LONGEVITY`; `hold_count` /
  `longevity_base`; fail-closed fallback to base rank when holds/amounts
  incomplete.
- `tw2002_aiclient/session/cli.py` — `tw chains --holds N` requests longevity
  on the yield base.
- `tests/test_chain_search.py`, `tests/test_cli_chains.py`
- this WO file

## Out of scope

- Autonomous loop rotation (forbidden).
- Inventing amounts / holds.
- Changing default L)chains / RANK_HOPS discovery order.

## Accept

1. `recompute(..., rank=RANK_LONGEVITY, hold_count=…)` calls
   `rank_chains_by_longevity` when port amounts + holds are known.
2. Missing holds / amounts → base rank unchanged (no crash, no invention).
3. `tw chains --holds` requests `RANK_LONGEVITY` with `longevity_base=yield`.
4. Focused pytest green; live-prove `n/a` (offline ranking).

## Proof

```bash
.venv/bin/python -m pytest tests/test_chain_search.py tests/test_cli_chains.py tests/test_chain_depletion.py -q -n0
```
