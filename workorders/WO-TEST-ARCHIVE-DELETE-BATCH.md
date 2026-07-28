# WO-TEST-ARCHIVE-DELETE-BATCH — delete twclient-hard-fail archive suites (BANK-DELETE)

**Status:** DONE · Cursor · PR #168 · awaiting hub Accept  
**Posted:** 2026-07-28T15:30Z · hub (from #149 AUDIT BANK-DELETE rows)

## Goal

Delete a small, disjoint set of ignored archive tests that hard-fail on `twclient` and have **no** reborn twin worth lifting — drop matching `--ignore=` lines. Same disposition class as #151/#153/#155.

## Scope (this slice — only these)

| File | Disposition |
|---|---|
| `tests/test_game_data.py` | BANK-DELETE |
| `tests/test_game_data_persist.py` | BANK-DELETE |
| `tests/test_game_knowledge.py` | BANK-DELETE |
| `tests/test_game_knowledge_learned_rules.py` | BANK-DELETE |
| `tests/test_miner.py` | BANK-DELETE |
| `tests/test_name_bank.py` | BANK-DELETE |

Plus matching `pytest.ini` `--ignore=` removals / comments citing this WO.

## Out of bounds

- `wo/WM-LANDMARKS-WRITE` / CC #165
- KEEP-IGNORED / BANK-REHAB rows (formations/state_parser already done)
- `tests/test_import_hygiene.py` vacuity strings

## Accept

1. Listed files deleted; ignores gone; suite green.
2. STATUS + tip SHA; live-prove `n/a`.

## Refs

- `workorders/AUDIT-TEST-IGNORE-LIST-LANDMINE.md`
