# WO-FIX-PLAY-CHAINS-TEST-STATE-ISOLATION

**Goal:** Hermeticize `tests/test_play_chains_discovered.py::_drive` so Play chains tests never read the operator's real `state/world/` for formations / dead-ends / class-pair fallback.

**Scope:**
- `tests/test_play_chains_discovered.py` (`_drive` only — product code untouched)
- this WO file

**Problem:** `_drive` already patches `known_sector_count`, but `world_stats.refresh` also calls `all_sectors` (dead-end/formations) and L)chains also runs `chain_detect.recompute` (pair-fallback hops). Left unpatched, assertions pass/fail based on how much the human has explored.

**Accept:**
1. `_drive` patches `world_model.all_sectors` → empty mapping, `explore.find_landmark_sectors` → `[]`, and `chain_detect.recompute` → empty pairs result (completed empty, not raise).
2. `tests/test_play_chains_discovered.py -n0` → all green on a machine with a populated `state/world/`.
3. No product/app/world_stats code changes.

**Proof:** `.venv/bin/python -m pytest tests/test_play_chains_discovered.py -n0 -q`
