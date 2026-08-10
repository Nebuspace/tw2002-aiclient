# WO-BUILD-FORMATIONS-GENESIS-RECOMMEND-VERIFY

**Status:** DONE (this PR)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/BUILD-FORMATIONS-GENESIS-RECOMMEND-VERIFY`
**gated:** no · **schema:** n/a

## Goal

Close the unused-code tip_check on `formations.recommend_genesis`: audit claimed
it was test-only while the LOCATE/CATALOG/RECOMMEND pass was otherwise live.
Verify-first, then give the free function a real product caller path.

## Verify-first (origin/main @ fb924dec)

- `recommend_genesis` returned `list(catalog.genesis_candidates)` and was only
  imported from `tests/test_formations_catalog.py`.
- Product paths (`explore.plan_find_formations`, `world_stats` genesis_count)
  read `.genesis_candidates` directly — behavior-identical to the free function,
  but left the symbol looking unwired to the unused-code tick.
- Not a missing algorithm: shortlist == `catalog.genesis_candidates`.

## Scope

- `tw2002_aiclient/explore.py` — route genesis shortlist through `recommend_genesis`
- `tw2002_aiclient/world_stats.py` — genesis_count via `recommend_genesis`
- `tw2002_aiclient/formations.py` — docstring tip-true
- `tests/test_explore.py` — monkeypatch spy pin + fake-catalog comment (#653 lesson)
- This workorder

## Accept

1. Product import graph reaches `recommend_genesis` from explore + world_stats.
2. Focused pin: `plan_find_formations` calls `recommend_genesis` (spy).
3. Existing formations / explore / world_stats tests green.
4. live-prove: n/a (offline planner / status refresh only).

## Proof

- `pytest tests/test_explore.py tests/test_formations_catalog.py tests/test_world_stats.py -q -n0`
- Full suite via CI
