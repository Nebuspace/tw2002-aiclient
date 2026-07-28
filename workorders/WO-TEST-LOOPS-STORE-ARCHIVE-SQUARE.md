# WO-TEST-LOOPS-STORE-ARCHIVE-SQUARE

**Goal:** Close the one site #188 left unmeasured: `tests/test_loops_store.py` archive-gated asserts (`skipif` *"archived store not present in this tree"*).

**Context:** Worktree checkouts lack the archived store path, so the floor at ~`:444` (`all(row["steps"] > 0 …)` and siblings) never ran under #188's mutation harness. Measure on a tree where `ARCHIVE_SKILLS.is_dir()` is true — typically the main checkout — or prove the skip fires everywhere and record that as the square (premise wrong).

**Deliverable:** Measured quantity + disposition (KEEP / BANK-FIX) for each previously-skipped site in that file that #188 would have covered. If the archive is absent on main too, say so explicitly — do not claim clean.

**Accept:**
1. Run (or prove skip-everywhere) the archive-gated non-temporal floor(s) from #188's declared gap.
2. Report measured value / skip-everywhere evidence; disposition.
3. live-prove `n/a`.

**Refs:** #188 appendix · `tests/test_loops_store.py` ~431–447 · CC CLAIM 20:10:20Z.
