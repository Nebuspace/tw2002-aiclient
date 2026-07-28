# WO-TEST-LOOPS-STORE-ARCHIVE-SQUARE

**Goal:** Close the one site #188 left unmeasured: `tests/test_loops_store.py` archive-gated asserts (`skipif` *"archived store not present in this tree"*).

**Context:** Worktree checkouts lack the archived store path, so the floor at ~`:444` (`all(row["steps"] > 0 …)` and siblings) never ran under #188's mutation harness. Measure on a tree where `ARCHIVE_SKILLS.is_dir()` is true — typically the main checkout — or prove the skip fires everywhere and record that as the square (premise wrong).

**Deliverable:** Measured quantity + disposition (KEEP / BANK-FIX) for each previously-skipped site in that file that #188 would have covered. If the archive is absent on main too, say so explicitly — do not claim clean.

**Accept:**
1. Run (or prove skip-everywhere) the archive-gated non-temporal floor(s) from #188's declared gap.
2. Report measured value / skip-everywhere evidence; disposition.
3. live-prove `n/a`.

**Refs:** #188 appendix · `tests/test_loops_store.py` ~431–447 · CC CLAIM 20:10:20Z.

---

## Findings — the square, closed (impl-claudecode-aiclient, 2026-07-28)

**Both halves of the WO's either/or are true at once, and that is the finding.**

### 1. The site measured — the floor is as tight as a floor can be

`ARCHIVE_SKILLS` resolves to `archive/pre-rebirth-2026-07-23/runtime/state/skills`, which
**does** exist in the main checkout, so the two gated tests run here. Measured directly
(read-only, no mutation needed — the quantity is a data property):

- `read_loop_store(...)` → `status=ok`, `unreadable=[]`, **16 blessed** (the `== 16` pin
  holds), 3 drafts.
- `all(row["steps"] > 0)` — steps across the 16: `[1, 1, 1, 7, 8, 10, 10, 10, 10, 11, 11,
  15, 16, 20, 45, 54]`. **True minimum 1 against a bound of 0.**

**Slack 1 — the tightest a floor over a positive integer count can be.** Three real
macros sit exactly one step above the bound, so a regression that zeroed any single
macro's step list would fire it. **KEEP.** #188's unmeasured square is clean on its
merits, not merely unexamined.

### 2. …and it is unreachable almost everywhere — that is the real defect

`archive/` is **gitignored** — `git check-ignore -v archive` → `.gitignore:56:archive/`
(asked git rather than inferred; the control on a tracked path correctly reports
nothing). Zero tracked files under it. Therefore:

| tree | archived store | the 2 gated tests |
|---|---|---|
| this machine's main checkout | present (untracked leftover) | **run** |
| every git worktree / lane | absent | skip |
| **CI** | absent — never cloned, it is ignored | **skip** |

CI run `30395046905` reports **2 skipped**, consistent with exactly these two. So
`test_reads_the_real_archived_artifacts_without_a_single_unreadable` — whose docstring
claims *"Proof the schema this reader accepts is the one the writer emits — 16 genuine
recorded macros, read as-is with nothing hand-fixed"* — is **proof that executes on one
developer's checkout and nowhere else**. Break the reader's schema handling and CI stays
green. A worktree certifies strictly less than the main checkout, and here CI certifies
less still — a sibling of the `pty_ui` exposure (139 tests) reported separately.

*A skipped test is not a failing test, which is exactly why this survives:* the suite
line reads `5586 passed, 2 skipped` and nobody reads two skips as a coverage hole.

### Fix to bank — `WO-TEST-ARCHIVE-CORPUS-FIXTURE`

Commit a small fixture corpus so the schema-conformance proof runs everywhere.
**Doctrine gate checked first, because the corpus is recorded game sessions:** the
directory is **84 K across 19 files**, and scans for `password|passwd|secret|token|
credential` and for host-shaped strings return **nothing** (with a benign-term control
confirming the scan reads all 19 files). It is safe to commit under
`canon/doctrine/secrets-and-credentials.md`.

Accept should require: the two tests **run** (not skip) in a fresh worktree and in CI;
the `== 16` pin either moves to the fixture's own count or is justified; and the
`skipif` either disappears or its reason is re-stated to describe what is genuinely
optional. If Max prefers the archive stay uncommitted, the alternative is to state in
the test's docstring that it is a **local-only** proof — the honest version of today's
silent skip.
