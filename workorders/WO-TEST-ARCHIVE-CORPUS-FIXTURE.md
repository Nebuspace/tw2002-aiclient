# WO-TEST-ARCHIVE-CORPUS-FIXTURE

**Goal:** Make the archive schema-conformance proof run in every worktree and in CI — not only on one developer checkout that happens to have a gitignored `archive/`.

**Scope:** `tests/` + a **committed** fixture corpus (hub GO 2026-07-28: commit the corpus; do not leave it as silent local-only).

**Context:** #193 — `archive/` is gitignored; the two `ARCHIVE_SKILLS.is_dir()`-gated tests skip in worktrees and CI. Floor itself KEEP (steps min=1). Doctrine scan: 84K / 19 files, no password|passwd|secret|token|credential, no host-shaped strings.

**Accept:**
1. Both previously gated tests **run** (not skip) in a fresh worktree and in CI.
2. `== 16` pin moves to the fixture's own count or is justified.
3. `skipif` gone, or reason describes something genuinely optional.
4. No secrets/host leakage in the committed corpus.

**Proof:** fresh worktree + CI show the tests collected and passed; suite. live-prove `n/a`.

**Refs:** #193 archive square · #194 sibling family · CC 20:23:58Z.
