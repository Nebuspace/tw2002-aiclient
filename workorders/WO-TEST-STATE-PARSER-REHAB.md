# WO-TEST-STATE-PARSER-REHAB — Port or supersede ignored state_parser suite

**Status:** BANKED · HIGH · Cursor-class OK  
**Posted:** 2026-07-28T04:32Z · from #149 ignore-list audit  
**Refs:** `tests/test_state_parser.py` (twclient collect-fail) · live `session/state_parser.py` · existing `test_state_sector_read.py`

## Goal
Either rewrite archive `test_state_parser.py` onto
`tw2002_aiclient.session.state_parser`, or prove live pins supersede it and
**delete** the ignored file + `--ignore` line with an honesty note.

## Accept
1. No silent ignore of the only broad parser suite if gaps remain vs canon.
2. Disposition recorded (rehab SHA or delete+gap table).
3. Suite + STATUS. live-prove n/a.

## Constraints
Explicit paths. Do not invent parser behavior. Avoid #147 chains.
