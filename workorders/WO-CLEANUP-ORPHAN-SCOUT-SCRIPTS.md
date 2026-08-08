# WO-CLEANUP-ORPHAN-SCOUT-SCRIPTS

**Goal:** `scripts/anet_step5_live_vs_fixture.py` and
`scripts/scout_game_select_classify.py` are throwaway one-off scout scripts
(both self-described as such in their own docstrings: "Offline… WO-ANET-
STEP5-LIVE-BYTES", "throwaway analysis, not product code") with zero
referencers anywhere in product or test code. `anet_step5_live_vs_fixture.py`
additionally hardcodes a now-nonexistent prior-session scratchpad path
(`/tmp/claude-501/.../scratchpad/anet-frame-A.json`) — it can no longer even
run. Remove both.

**Scope:**
- `scripts/anet_step5_live_vs_fixture.py` — deleted
- `scripts/scout_game_select_classify.py` — deleted
- this WO file

**Out of scope:** any other `scripts/` entry — only these two, re-grepped
immediately before deletion.

**Constraints:** verify-first — re-grepped the whole tree (product code,
tests, docs) for both filenames/module-level symbols before deleting;
zero hits outside the files themselves and stale worktree copies.

**Accept:** both files removed; full test suite unaffected (neither was
imported or invoked by any test).

**Proof:** `git grep -l "anet_step5_live_vs_fixture\|scout_game_select_classify"` → no hits outside removed files. `.venv/bin/python -m pytest -n auto -q` unaffected by this change (pre-existing PTY flakes only, unrelated).
