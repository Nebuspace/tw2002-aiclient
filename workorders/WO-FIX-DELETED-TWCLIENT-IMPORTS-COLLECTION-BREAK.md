# WO-FIX-DELETED-TWCLIENT-IMPORTS-COLLECTION-BREAK — BANK-DELETE four twclient-hard-fail suites

**Status:** IN FLIGHT · Cursor · `wo/FIX-DELETED-TWCLIENT-IMPORTS-COLLECTION-BREAK`  
**Posted:** Cycle-45 HIGH · queue-aiclient.md

## Goal

Remove four ignored test files that still `from twclient import …` after ADR-001 deleted the sibling package — they cannot collect on tip. No rebirth-era CLI/protocol surface matches what they pin.

## Disposition (verify-first)

| File | Why BANK-DELETE (not rewrite) |
|---|---|
| `tests/test_cli_crawl_wiring.py` | Pins `cli.cmd_crawl` / `crawl` subparser — tip `session/cli.py` has neither (G2 deliberately left daemon/CLI crawl unwired; live crawl coverage is `test_menu_crawler.py` + `test_crawl_driver.py`) |
| `tests/test_cli_haggle_wiring.py` | Pins `cli.cmd_haggle` / `haggle` verb — absent on tip |
| `tests/test_protocol_haggle.py` | Pins `protocol.dispatch(..., "haggle", …)` — `session/protocol.py` docstring: `haggle` remains a later WO; engine coverage is `tests/test_haggle.py` → `session.haggle` |
| `tests/test_replay_ledger_integration.py` | Pins `twclient.skills` + protocol replay ledger path — skills module gone; protocol lists `replay`/`list_skills` as later WOs |

Same class as #168–#176 archive DELETE batches. Drop matching `--ignore=` lines in `pytest.ini`.

**REVISE (hub REJECT #474):** `action_safety.COVERAGE` `guard_id=start_anchor` pointed at the deleted file's `start_anchor_mismatch` marker. Live proof already lives in `tests/test_loop_player.py` (`HALT_START_ANCHOR_MISMATCH == "start_anchor_mismatch"` + replay_loop mismatch cases). Repoint `proof_test_relpath` there — do **not** restore the archive suite.

## Out of bounds

- `tests/test_crawl_start_protocol.py` (still KEEP-IGNORED — daemon crawl verb)
- `tests/test_haggle.py` / `tests/test_ledger.py` / `tests/test_analyze.py` (other ignore rows)
- Restoring crawl/haggle CLI verbs

## Accept

1. Four files deleted; four `--ignore=` lines gone; suite collects clean (0 ERRORS).
2. STATUS + tip SHA; live-prove `n/a` (offline suite hygiene).

## Refs

- ADR-001 · `workorders/WO-TEST-SUITE-REHAB.md` · Cycle-45 queue row
