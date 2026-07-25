# WO-MT-04-WATCH-FRAME-SWALLOW

**Status:** DONE · origin `397f11d`  
**Posted:** 2026-07-25T20:04:13Z · Accepted 2026-07-25T20:30:06Z

## Goal

`tw watch` honesty on unparseable NDJSON frames (SESSION-F8 / MT-04).

## Scope

- `tw2002_aiclient/cli.py` (watch path)
- `tests/test_cli_ops_verb_e2.py`

## Accept

Corrupt line between two valid events → operator-visible skip/error **or** hub-Accepted explicit gap pin; `--frames N` accounting honest.

## Proof

Landed origin `397f11d`. Product tell `ERROR: watch_frame_unparseable`.

## Refs

- `workorders/AUDIT-MISSING-TESTS.md` MT-04
- SESSION-F8
