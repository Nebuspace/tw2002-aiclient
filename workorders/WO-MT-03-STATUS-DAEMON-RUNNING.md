# WO-MT-03-STATUS-DAEMON-RUNNING

**Status:** DONE · origin `b2ef693`  
**Posted:** 2026-07-25T19:25:18Z · Accepted 2026-07-25T20:30:06Z

## Goal

Fix `tw status --json` claiming `daemon_running: True` after a failed status round-trip (SESSION-F7 / MT-03).

## Scope

- `tw2002_aiclient/cli.py` (`cmd_status`)
- `tests/test_cli_status_daemon_running_honesty.py` (new)

## Accept

With pidfile-alive + status round-trip failing, JSON must **not** claim `daemon_running: True` (or pair with explicit `status_unreachable`); rc stays non-zero; tests pin both honest-down and false-True-regression.

## Proof

Landed origin `b2ef693`. Spot-proved honesty + ops-verb-e2.

## Refs

- `workorders/AUDIT-MISSING-TESTS.md` MT-03
- `canon/findings.md` SESSION-F7
