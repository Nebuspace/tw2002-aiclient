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


**HANDOFF:** slice 2 — implement on this branch (2026-07-28 hub).

---

## Outcome (2026-07-28, `impl-claudecode-aiclient`)

Built in a worktree that has **no `archive/` at all**, so every number below is a
genuine fresh-tree measurement rather than a simulation of one.

### What changed

| | before | after |
|---|---|---|
| corpus path | `archive/pre-rebirth-2026-07-23/runtime/state/skills/` (**gitignored**, `.gitignore:56`) | `tests/fixtures/loop_store_archive/` (tracked) |
| corpus contents | 19 files | the same 19 files, **copied byte-for-byte** (md5 verified per file) |
| gate | `@pytest.mark.skipif(not ARCHIVE_SKILLS.is_dir(), …)` ×2 | gone — `_archived_macro_corpus()` asserts, so a missing corpus is a named red |
| `tests/test_loops_store.py` | 28 passed, **2 skipped** | **31 passed, 0 skipped** |
| suite under the CI filter | 5592 collected, 5590 passed, 2 skipped | 5593 collected, **5593 passed, 0 skipped** |

The corpus was **copied, not trimmed.** The claim these tests make is *"read as-is
with nothing hand-fixed"*; a trimmed corpus would have saved 84 K by quietly
weakening the one sentence the tests exist to support.

### Why `== 16` stays a literal, and gains a second half

16 is the count of `*.json` the archive writer left at the corpus root (3 more sit
under `_drafts/`). The pin is now **two** assertions that fail on different things:

- `len(blessed) == 16` — notices a **corpus file disappearing**.
- `len(blessed) == len(_corpus_json())` — notices the **reader dropping a file** it
  should have read.

A derived count alone is blind to deletion: the corpus and the expectation shrink
together and still agree. F3 below is the measurement of exactly that.

A third test, `test_the_committed_corpus_is_the_whole_archived_store`, pins the
inventory itself (16 + 3, `_drafts` the only subdirectory) so the two counts above
are a claim about the *reader* rather than about whatever happens to be on disk.
`_corpus_json()` uses `os.listdir`, not `Path.glob`, for the reason `store.py:247`
already spells out — `glob` swallows a directory `PermissionError` and returns
empty, so a cross-check built on it can silently agree with anything.

### Falsification — every pin injected, targeted red observed, restore md5-identical

| | injected defect | result |
|---|---|---|
| **F1** | corpus directory hidden (the exact condition that used to skip) | 3 failed / 28 passed — `test_the_committed_corpus_is_the_whole_archived_store`, `test_reads_the_real_archived_artifacts_without_a_single_unreadable`, `test_real_mined_draft_reports_the_stat_it_actually_has` |
| **F2** | one corpus file deleted (`aegis_organics_loop.json`) | 2 failed / 29 passed |
| **F3** | same deletion **plus** the literal "repaired" 16 → 15 — the realistic hurried fix | 1 failed / 30 passed: only the inventory test. The derived equality passed at 15 == 15, which is the deletion-blindness above, measured |
| **F4** | the archive's own renderer bug reinstated (`list_view.py` per-turn only, dash swallows a real `cr_per_action`) | 1 failed / 30 passed — `test_real_mined_draft_reports_the_stat_it_actually_has` |

### The before/after that makes the case

F4's defect was run **twice in this same archive-free worktree**, same interpreter,
same fixture, changing only the test file:

- **old, `skipif`-gated file:** `28 passed, 2 skipped` — exit 0. The defect is real,
  present, and completely invisible.
- **new file:** `1 failed`.

That is the whole WO in one comparison. The skip was not a small gap in coverage; it
was the *absence* of the proof in every place the proof would ever have been read —
no worktree had the corpus, and CI cannot clone an ignored path. And a skip count is
not a number anyone audits, which is how it survived.

### Doctrine

Corpus re-scanned before commit: 43 distinct recorded `input` values, all 1–5 char
sector numbers or single keys; zero credential-shaped inputs; no host-shaped strings;
no operator-home paths. Names are TW2002 sectors plus the profile name `aegis`, which
the hub GO'd to keep.

### Proof

- `tests/test_loops_store.py` in a fresh (archive-free) worktree: 28 passed / 2 skipped → **31 passed, 0 skipped**.
- Exact CI invocation `pytest -m "not live_login and not pty_ui"` with `pytest.ini` addopts intact: **5593 passed, 0 skipped, 0 errors**, exit 0, tree fingerprint unchanged across the run.
- `pytest -m pty_ui`: 139 passed (the changed file carries 0 `pty_ui` markers, so the standing rule does not bind here; run anyway).
- Live: `n/a` — no daemon, no TWGS, no sends on any path this WO touches.

### Instrument note

The first whole-suite run reported 9 collection errors. They were mine: `-o addopts=`
replaces the ini's `addopts` wholesale, which **strips the `--ignore` list** and
un-ignores nine archive-era `import twclient` modules CI never collects. `-o addopts=`
is safe for a single named file and wrong for a suite certification — the run that
certifies has to be the run CI performs. Same family as the `-q` stacking to `-qq`
from #188.
