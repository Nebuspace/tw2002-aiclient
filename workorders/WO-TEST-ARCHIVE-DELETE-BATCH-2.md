# WO-TEST-ARCHIVE-DELETE-BATCH-2 — delete more twclient-hard-fail archive suites

**Status:** DONE · Cursor · PR #171 · awaiting hub Accept  
**Posted:** 2026-07-28T15:48Z · hub (Cursor ask · #149 AUDIT BANK-DELETE)

## Goal

Same class as #168: delete ignored archive tests with no reborn twin; drop matching `--ignore=` lines.

## Scope (only these)

| File | Disposition |
|---|---|
| `tests/test_probe.py` | BANK-DELETE |
| `tests/test_ship_upgrade_decision.py` | BANK-DELETE |
| `tests/test_skills.py` | BANK-DELETE |
| `tests/test_intervention_labels.py` | BANK-DELETE |
| `tests/test_introspector.py` | BANK-DELETE |
| `tests/test_integration_introspect_persist.py` | BANK-DELETE |

Plus `pytest.ini` ignore removals + comment citing this WO.

## Out of bounds

- CC #169 / LAST-KNOWN-SECTOR
- KEEP-IGNORED / BANK-REHAB rows
- `tests/test_import_hygiene.py` vacuity strings
- LIVE-PROVE HANDOFFs (pause this WO if hub posts LIVE-PROVE)

## Accept

1. Listed files deleted; ignores gone; suite green.
2. STATUS + tip SHA; live-prove `n/a`.

## Refs

- `AUDIT-TEST-IGNORE-LIST-LANDMINE.md` · #168
