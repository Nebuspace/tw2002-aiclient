# WO-CLEANUP-DEAD-EXPLORE-OFFER-ACTION-CONSTANT

**Goal:** Retire unused `_EXPLORE_OFFER_ACTION = "Explore"` in `tw2002_aiclient/app.py`
(zero product/test references; siblings `_EXPLORE_OFFER_CLASSIFICATION` / `_EXPLORE_OFFER_KEYS`
remain live).

**Scope:** `tw2002_aiclient/app.py` (+ this WO).

**Depends-on:** none

**Accept:**
- Constant gone; `rg _EXPLORE_OFFER_ACTION` empty
- Explore offer / StarDock confirm paths unchanged (`_EXPLORE_STARDOCK_ACTION` still used)

**Proof:** focused pytest on cockpit explore/armconfirm if present; live-prove `n/a` (dead constant delete).
