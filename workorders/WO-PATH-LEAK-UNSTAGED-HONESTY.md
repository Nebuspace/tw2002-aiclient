# WO-PATH-LEAK-UNSTAGED-HONESTY — path-leak-scan must not exit 0 on "nothing staged"

**Status:** OPEN · EXECUTE · tooling · Cursor-only  
**Posted:** 2026-07-27T20:50:00Z · hub from CC #114 STATUS finding  
**Seeded for execute:** 2026-07-30T03:25Z · hub · autonomous safe queue after #232  
**Seat:** impl-aiclient-cursor  
**Depends:** none  
**Refs:** CC 2026-07-27T20:20 · `scripts/path-leak-scan.sh` · pre-commit still OK post-stage

## Goal

Manual `path-leak-scan.sh` with dirty-but-unstaged work prints "no staged changes" and exits **0** — indistinguishable from a real clean pass. Change to non-zero (or explicit FAIL) when the working tree has unstaged/untracked modifications and the index is empty, **or** scan the working tree when invoked with a documented `--worktree` / default-preflight mode.

## Scope

- `scripts/path-leak-scan.sh` (and a tiny pin script under `scripts/` or `tests/` if one already houses shell pins)
- docs in the script header / usage only — no product code

## Constraints

- Pre-commit staged path must keep working (exit 0 on clean staged; non-zero on staged leak).
- Do not invent a second leak scanner; extend this one.
- No product / UI / canon / deps / `app.py` (#218 frozen).
- live prove = `n/a` (tooling only).

## Accept

1. Vacuous "nothing staged" is **not** exit 0 when the tree is dirty (or the tool refuses with a clear message + non-zero).
2. Staged clean path still exits 0; staged leak still exits non-zero (negative control).
3. Pre-commit post-stage path unchanged / still fires.
4. Focused pin + STATUS naming the chosen behavior (`--worktree` vs dirty-index refuse).

## Proof

Scripted inject: dirty unstaged with a fake operator-home absolute path → must not look green; staged leak → fail; staged clean → pass.

```bash
# illustrate; exact pin lives with the change
bash scripts/path-leak-scan.sh            # dirty unstaged → non-zero or scans worktree
bash scripts/path-leak-scan.sh --file …   # still works
```
