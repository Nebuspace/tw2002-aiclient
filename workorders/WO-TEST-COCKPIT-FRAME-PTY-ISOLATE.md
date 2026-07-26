# WO-TEST-COCKPIT-FRAME-PTY-ISOLATE

**Status:** OPEN · Cursor preferred (tests lane)  
**Posted:** 2026-07-26T00:55:00Z

## Goal

Stop `test_cockpit_frame_pty::test_full_tier_center_viewport_is_double_line_and_empty_panels_honest` from reading the **ambient daemon**. While an operator plays, the GAME viewport paints real content → suite red for every seat (measured: daemon live FAIL / stopped PASS / clean checkout PASS).

## Scope

- `tests/test_cockpit_frame_pty.py` (and helpers)
- Isolated `run_dir` / fake session — **not** the repo default `run/`

## Constraints

- Do not "fix" by weakening the blank-viewport assertion
- Do not stop/kill Max's live daemon as a test precondition
- Product cockpit paint unchanged unless a real bug is proven (announce)

## Accept

Full-suite (or this file under `-n auto`) green **with ambient daemon connected**; assertion still fails if the *isolated* viewport incorrectly paints content.

## Proof

STATUS + SHA · before/after with daemon live · cite CC disclosure 2026-07-25T22:32Z.

## Refs

CC HEADS-UP ambient-daemon fail · SCREENS-CREATE-FORM-SPLIT sibling note · FakeTWGS / run_dir patterns
