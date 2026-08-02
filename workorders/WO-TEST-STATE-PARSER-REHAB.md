# WO-TEST-STATE-PARSER-REHAB — Delete archive parse_state suite

**Status:** DONE · origin `2defd0f` (#153) · tip-honesty stamp 2026-08-02 (product on main; banner was stale SEAT-DONE awaiting Accept)
**Posted:** banked #149 · EXEC after #151 · seat STATUS 2026-07-28T04:50Z  
**Refs:** AUDIT-TEST-IGNORE-LIST-LANDMINE.md · #151 DELETE lesson

## Disposition: **DELETE** (not rehab)

Evidence:
1. Ignored file imported **`twclient.state_parser`** (`parse_state`, `parse_port_report`, …) — that package/API is gone.
2. Reborn producer is **`tw2002_aiclient.session.state_parser`** with a different contract (`read_current_sector` / `read_warps_*` / `read_port_*` / `read_credits_*` typed reads).
3. Live collected coverage already exists and is green: `tests/test_state_sector_read.py` (24) · `tests/test_state_parser_port_flyby.py` (13).
4. Porting the 876-line archive suite would invent an adapter layer over deleted APIs — same class of lie as #151 stub consumer.

## Accept met
1. Deleted `tests/test_state_parser.py`; dropped `--ignore=tests/test_state_parser.py`.
2. Import-hygiene vacuity pins untouched.
3. Live parser suites green; live-prove n/a.

## Constraints
No stubs. No twclient. Fixtures retained (shared). Avoid #147.
