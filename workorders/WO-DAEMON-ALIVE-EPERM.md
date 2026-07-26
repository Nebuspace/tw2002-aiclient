# WO-DAEMON-ALIVE-EPERM

**Status:** DONE · origin `17adc2a`  
**Posted:** 2026-07-25T20:30:06Z

## Goal

`daemon_alive` must not treat `PermissionError` (EPERM — process EXISTS) as absent. Today it folds into `False` → `ensure_raw` can **spawn a second daemon** (single-connection hard rule breach); `cmd_stop` rc0 "not running"; status/menumap lie.

## Scope

- `daemon_alive` (+ callers if needed)
- New tests distinguishing ESRCH vs EPERM
- Worktree off `origin/main` (`397f11d`+)

## Constraints

- After MT-09/12 or immediately if those are thin — **Cursor owns `cli.py`**; CC correctly refused to touch it mid-lane.
- Third answer for unreadable pidfile OK (not fold into absent).

## Accept

- EPERM → alive/`True` (or explicit `alive_unsignalable`)
- ESRCH → `False`
- `ensure` does **not** spawn when EPERM
- `stop` does not claim success-noop
- Tests pin both

## Proof

Targeted pytest + STATUS.

## Refs

- CC HEADS-UP @ 2026-07-25T20:12:02Z
- MT-03 F7 PID-reuse adjacency
