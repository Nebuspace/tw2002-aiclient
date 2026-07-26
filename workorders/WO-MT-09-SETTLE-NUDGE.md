# WO-MT-09-SETTLE-NUDGE

**Status:** DONE · origin `9110a95`  
**Posted:** 2026-07-25T20:04:13Z

## Goal

Pin attach settle-nudge `send_request("read")` discard is benign (MT-09).

## Scope

- `tests/test_cli_attach_settle_nudge.py` (new)
- Touch product only if checking is the right fix — prefer pin-first
- Worktree off `origin/e42eb31` (rebase as tip moves)

## Constraints

No classify.

## Accept

Nudge failure does not flip attach rc (or product starts checking + test follows).

## Proof

Targeted pytest + STATUS.

## Refs

- `workorders/AUDIT-MISSING-TESTS.md` MT-09
- SESSION-F1-MICRO-SETTLE-NUDGE
