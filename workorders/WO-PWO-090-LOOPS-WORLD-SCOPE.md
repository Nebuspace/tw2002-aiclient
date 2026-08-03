# WO-PWO-090-LOOPS-WORLD-SCOPE — Macro / loop library world-scoped paths + migrate-on-read

**Status:** build  
**Hub GO:** 2026-08-03T12:56:30Z (migrate WO required first — DECISION explicit)  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/PWO-090-LOOPS-WORLD-SCOPE`

## Goal

Close the `canon/engine/world-identity.md` divergence that left the taught-macro library flat under `state/skills/` while every other durable world store lives under `state/world/<world_id>/…`.

## Scope

- `tw2002_aiclient/loops/store.py` — `loops_dir` / `drafts_dir` take optional `world_id`; `migrate_flat_loops_to_world`; `read_loop_store(..., world_id=)`
- `tw2002_aiclient/loops/loader.py` · `recorder.py` — same `world_id` seam + migrate before I/O
- Product wiring: `app.py` (L-list + Record save), `session/autoloop.py` (profile-derived), `session/cli.py` (`tw loops|record --world-id`), `miner.py`
- Canon: `DECISION-LOOPS-WORLD-MIGRATE-ON-READ` in `canon/DECISIONS.md`; tip update in `canon/engine/world-identity.md` + PREP stamp
- Tests: path + migrate + read-after-migrate in `tests/test_loops_store.py`

## Out of scope

- Deleting the legacy flat tree after migrate
- Trace-ledger world-scoping (separate divergence in world-identity)
- PWO-088 Option B / PWO-106/107

## Accept

1. With `world_id`, paths resolve to `state/world/<id>/skills/` (+ `_drafts/`).
2. First world-scoped read/write copies flat → world when world empty and flat non-empty; idempotent; flat preserved.
3. Without `world_id`, behavior stays flat (no surprise migrate).
4. DECISION cites migrate-on-first-read (not silent exemption).
5. Offline tests cover path + migrate; live-prove **n/a**.

## Proof

```bash
.venv/bin/python -m pytest tests/test_loops_store.py -q -k 'world_scoped or migrate or stays_flat'
```

Live-prove: **n/a** (filesystem scoping; no live send / TWGS).

## Refs

- Hub GO · `DECISION-LOOPS-WORLD-MIGRATE-ON-READ`
- `canon/engine/world-identity.md` §Code divergence
- `workorders/WO-P7-090-096-world-substrate-PREP.md` PWO-090
