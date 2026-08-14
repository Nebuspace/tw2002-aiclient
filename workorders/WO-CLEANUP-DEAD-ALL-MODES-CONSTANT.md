# WO-CLEANUP-DEAD-ALL-MODES-CONSTANT

**Goal:** Retire unused `_ALL_MODES` frozenset in `session/control_lock.py`
(zero callers; `_SETTABLE_MODES` remains the live set).

**Scope:** `tw2002_aiclient/session/control_lock.py` (+ this WO).

**Depends-on:** none

**Accept:**
- `_ALL_MODES` gone; `rg _ALL_MODES` empty in product tree
- `MODE_*` constants and `_SETTABLE_MODES` unchanged

**Proof:** `pytest tests/test_control_lock.py`; live-prove `n/a` (dead constant delete).
