# WO-TUI-KILLPG-EPERM-CURSES-PTY

**Status:** DONE · PR #18 · origin `759f6bd` (was READY-FOR-REVIEW · Cursor · hub-seeded `wo/TUI-KILLPG-EPERM-CURSES-PTY` · depends on TUI-SPIN DONE on main)
**Depends:** `WO-TUI-DEAD-TERMINAL-SPIN` landed (PR #2) — loud `warnings.warn` on EPERM is the instrument  
**Seat:** CC preferred (isolation already done on that lane)

## Goal

Explain and fix (or honestly bound) `os.killpg` → `PermissionError` that fires **reliably on curses-in-pty children** under `start_new_session=True`, causing process-group cleanup to degrade to direct-child kill (grandchildren not reaped).

## Known evidence (do not rediscover)

- ~88 EPERM warnings per full suite on the cert machine when curses-in-pty teardown runs
- Plain `sleep` children with identical pty/`setsid` shape: **0** EPERM (negative fixture was worthless)
- Reproduces under `-n0` and `-n auto`
- Measured leak today: **none** when child holds no live grandchild at teardown; latent when curses child holds a real `twd`

## Accept

1. Root-cause note (or narrowed "unknown but bounded" with reproduction recipe) in `audit/`
2. Product fix **or** documented platform carve-out that does not overclaim "reaps the whole group"
3. Pin that fails if EPERM path goes silent again; pin that curses-in-pty path still terminates without hang

## Proof

pytest pins + STATUS citing the audit note. No invent screen classes.

## Refs

- CC STATUS 2026-07-26T18:00:47Z disclosure #2 + CORRECTION 18:02:30Z
- `WO-TUI-DEAD-TERMINAL-SPIN` / PR #2
