# WO-CLEANUP-LOGS-DIR-ROTATION

**Status:** DONE (gitignore coverage confirmed — no repo rotation required)
**Priority:** LOW
**Gated:** no

## Goal

Cycle-42 flagged ~807 local session log files (~406 empty, ~12MB) under `logs/`
with no cleanup/rotation. Decide: add rotation, or confirm `.gitignore` already
keeps them out of the repo.

## Verify-first (tip `22b799b`)

| Check | Result |
|---|---|
| `.gitignore` line 3 | `logs/` |
| `git check-ignore -v logs/session.log` | ignored via `.gitignore:3:logs/` |
| `git ls-files logs` | **0** tracked paths |

Session logs are **local-only**; they cannot land in a commit via normal add.
Repo hygiene debt is closed by this confirmation. Optional local rotation (mtime
prune of empty/old files) remains operator-side tooling — out of scope for this
tip-close; bank a future LOW WO only if Max wants an automated prune script.

## Accept

1. WO records the gitignore / zero-tracked evidence above.
2. No product code change.
3. live-prove: n/a.
