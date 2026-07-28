# WO-TEST-EMITTED-SCAN-IDENTITY

**Goal:** Replace the vacuous producer-population floor with identity anchors.

**Scope:** `tests/test_status_vocabulary_guard.py`

**Accept:**
1. The emitted side names real producer files (at minimum `session/protocol.py`, `world_model.py`) as `:167` already does for consumers.
2. Removing `session/protocol.py` from the scan reddens *this* test, not only its starved sibling.
3. The floor is not merely raised — a bigger number keeps the wrong instrument (#185).

**Proof:** injected scan-loss reddens; suite. live-prove `n/a`.

**Refs:** #188 F1 · #186 badge identity pattern.
