# WO-TEST-CI-SKIP-COUNT-GUARD — rising pytest skips must fail CI

**Status:** OPEN · EXECUTE · tooling · Cursor-only  
**Posted:** banked on hub-skip-guard worktree · **Seeded for execute:** 2026-07-30T03:38Z · hub  
**Seat:** impl-aiclient-cursor  
**Depends:** none (CI/tooling)  
**Refs:** CC 21:03:17Z · #197 · #194 (deselect is a different door)

## Goal

Make a rising pytest **skip** count fail CI instead of hiding in a summary
line nobody audits. After #197, CI reports thousands passed and **0 skips**.
This guard pins **skipped == 0**. Deselect (`pty_ui`) remains #194's lane —
do not conflate skip with deselect.

## Scope

- `.github/workflows/suite.yml` — ensure junitxml is written; add a follow-on
  step that fails on `skipped != 0`
- small check script under `scripts/` (parse junitxml; fail closed on missing /
  truncated / implausible `tests` count)

## Constraints

- No product code / UI / canon / deps / `app.py` (#218 frozen).
- Guard **fails** if XML missing/truncated or `tests` attribute is not in the
  expected thousands **before** reading skipped (absence must not green).
- Pin at **0** skips (not "no worse than today").
- Name is skip-count, not coverage.
- live prove = `n/a`.

## Accept

1. Suite step writes junitxml; following step fails if `skipped != 0`.
2. Guard fails closed on missing/truncated XML or implausible test count.
3. Injected `@pytest.mark.skip` reddens the guard; tip stays green; inject
   removed md5-identical.
4. Focused pin script + STATUS; full suite still green on tip.

## Proof

```bash
# house pin — inject → fail → remove → green (exact path in STATUS)
bash scripts/test_ci_skip_count_guard.sh   # or equivalent named in STATUS
```

## Hazards

- XML absence must not green
- deselect ≠ skip (#194)
- do not weaken suite collection to dodge the pin
