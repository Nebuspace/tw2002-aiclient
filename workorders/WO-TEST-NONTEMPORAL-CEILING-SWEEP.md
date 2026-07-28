# WO-TEST-NONTEMPORAL-CEILING-SWEEP

**Goal:** Mirror of #188 for **ceilings** (`<=` / `<`): find count/size/ratio bounds so *generous* that growth (or the bad direction) cannot cross them — vacuous ceilings rather than vacuous floors.

**Context:** #188 measured 57 non-temporal floors; ceilings were enumerated but not individually measured. Same instrument defects to avoid (token-boundary exclusions; purge `__pycache__` + `.pytest_cache` per mutation; md5-restore).

**Deliverable:** Sweep report (STATUS and/or appendix on this WO) with measured quantity per ceiling site, disposition KEEP / BANK-FIX / FIXED-inline-if-trivial. Bank fix WOs for real defects. **No product code** unless a one-line test fix is Accept-complete.

**Accept:**
1. Report covering non-temporal ceilings in `tests/`.
2. Each suspect: measured value, bound, what silent growth/miss looks like, disposition.
3. live-prove `n/a` (docs/test measurement).

**Refs:** #188 appendix · CC CLAIM 20:10:20Z.
