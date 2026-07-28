# WO-TEST-FORMATIONS-REHAB — Delete orphan formations test (no producer)

**Status:** SEAT-DONE · awaiting hub Accept · Cursor (`impl-aiclient-cursor`)  
**Posted:** banked #149 · EXEC · **REVISE (a) DELETE** hub 2026-07-28T04:41:32Z · seat STATUS 2026-07-28T04:42Z  
**Refs:** ignore-list audit HIGH · #142 · CC evidence (no formations producer on tip) · port bank #152

## Goal
**(a) DELETE** `tests/test_formations.py` — consumer with no in-tree producer.
Stub/`catalog_provider` doubles in that file = #142-class lie. Planner seam pins
remain in `tests/test_explore.py`. Do **not** invent `catalog_world`.

## Accept
1. `tests/test_formations.py` deleted.
2. No `--ignore=tests/test_formations.py` in `pytest.ini`.
3. Do not touch `tests/test_import_hygiene.py` vacuity strings (`:109`, `:115`).
4. Suite green; live-prove n/a.

## Constraints
No twclient resurrect. No stub producer. Avoid #147. Port path = banked PR #152.
