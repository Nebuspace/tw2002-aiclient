# WO-CLEANUP-LOGS-DIR-ROTATION

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** LOW (Cycle-48 disk-hygiene)  
**Depends-on:** none

## Goal

Close the session-log disk-hygiene debt: confirm `logs/` never enters git,
and provide an optional local rotator for the empty/aged `session-*.log`
files `TranscriptLogger` creates at daemon start.

## Evidence (verify-first)

1. `.gitignore` line 3: `logs/` — confirmed.
2. `git ls-files logs/` → **0** tracked paths.
3. Local seat sample (not committed): ~807 files · ~406 zero-byte · ~12M —
   start-creates-file pattern from `session/logging_util.py` `TranscriptLogger`.

## Scope

- `scripts/rotate-session-logs.sh` — delete 0-byte `session-*.log`; optional
  `--days N` age prune; `--dry-run`; never stages/commits
- this WO file

## Accept

1. `logs/` remains gitignored; zero tracked files under `logs/`.
2. `scripts/rotate-session-logs.sh --dry-run` exits 0 against an empty or
   missing log dir (and against a real `logs/` when present).
3. Script only matches `session-*.log` under the chosen log dir (`--log-dir`
   or repo `logs/`).

## Proof

```bash
git check-ignore -v logs/
git ls-files logs/ | wc -l   # expect 0
bash scripts/rotate-session-logs.sh --dry-run
bash -n scripts/rotate-session-logs.sh
```

Live-prove: **n/a** (local hygiene script + gitignore confirm; no session path).
