# WO-TEST-CI-SKIP-COUNT-GUARD

**Goal:** Make a rising pytest **skip** count fail CI instead of hiding in a summary line nobody audits.

**Context:** After #197, CI reports 5593 passed and **0 skips**. Deselect (`pty_ui`) is a different door (#194). This guard covers **skipped** only.

**Scope:** `.github/workflows/suite.yml` + small check script. No product code.

**Accept:**
1. Suite step writes junitxml; following step fails if `skipped != 0`.
2. Guard **fails** if XML missing/truncated or `tests` attribute not in the expected thousands (before reading skipped).
3. Pin at **0** (not "no worse than today").
4. Injected `@pytest.mark.skip` reddens the guard; tip green; inject removed md5-identical.
5. live-prove `n/a`.

**Hazards (must stay in WO):** XML absence must not green; name is skip-count not "coverage"; deselect is #194's lane.

**Refs:** CC 21:03:17Z · #197 · #194.
