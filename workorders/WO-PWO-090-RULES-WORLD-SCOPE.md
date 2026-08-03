# WO-PWO-090-RULES-WORLD-SCOPE — Reflex rules world-scoped paths + migrate-on-read

**Status:** DONE · merged `698003e` (#364) · tip-honesty stamp after Accept
**Hub GO:** 2026-08-03T13:12:30Z
**Seat:** impl-aiclient-cursor
**Branch:** wo/PWO-090-RULES-WORLD-SCOPE

## Goal
Same mechanical class as #362 loops: colocate `state/rules` under `state/world/<id>/rules/` with explicit migrate-on-first-read.

## Scope
- `tw2002_aiclient/rules/store.py` — world_id paths + migrate_flat_rules_to_world
- `tw2002_aiclient/rules/writer.py` · `rules/cli.py` · `app.py` (U)rules + analyze bless)
- DECISION-RULES-WORLD-MIGRATE-ON-READ · tip note in world-identity.md
- tests

## Out of scope
- Ledger world-scope (HOLD)
- PWO-106/107 · PWO-088 B

## Accept
1. world_id → state/world/<id>/rules/
2. migrate flat→world when world empty; idempotent; flat preserved
3. omit world_id → flat
4. DECISION cited; offline tests; live-prove n/a

## Proof
pytest tests/test_rules_store.py tests/test_rules_writer.py -q
