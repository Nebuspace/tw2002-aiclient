# WO-P2-G2-MENU-CRAWLER — Menu dialogue-graph crawler (SAFE_ALLOWLIST, read-only, no state-change keys)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-25 · tip **`1198dce`** (CC · Fable 5; G2 1/2 `438ef10` + G2 2/2 safe-emit choke)
> Type: build · Phase: 2 · Seat: impl-claudecode-aiclient (Fable)
> Refs: `WO-P2-OPS-VERB-G-PREP.md` G2 · `canon/doctrine/action-safety-guards.md` SAFE_ALLOWLIST

## Goal
Port menu crawler that discovers dialogue graph / writes knowledge map — SAFE_ALLOWLIST / no state-changing keys. Engine-first: crawler module(s) under `tw2002_aiclient/menu/` + proving tests (rehab `test_menu_crawler` / `test_crawl_*` greenfield). CLI allowlist/`cli.py` wire after `lane-cli-encode` releases `cli.py`. G2 (1/2) landed engine `438ef10`; G2 (2/2) landed safe-emit choke `1198dce`.

## Scope
- New crawler modules under `tw2002_aiclient/menu/`
- Thin `crawl_driver` if archive shape requires
- `tests/test_menu_crawler.py` + `test_crawl_*.py` (greenfield proving tests; un-ignore as they go green)
- CLI wire to `cli.py` after lane-cli-encode resolves

## Constraints
- `SAFE_ALLOWLIST`: crawl uses ONLY navigation keys; no STATE_CHANGING_KEYS emitted
- Archive reference-only; no `import twclient`
- No `git stash` (multi-seat tree)
- Commit finished-lane blobs before long review cycle
- G3/G4 serialize behind G2 Accept

## Accept
1. Crawler proves allowlist: never emits `STATE_CHANGING_KEYS`
2. Knowledge write path honest (no fake rows)
3. Suite green (crawler tests un-ignored as they pass)
4. Safe-emit choke proven by attacking it (G2 2/2)

## Proof
Isolated cert + STATUS SHA. G2 2/2: safe-emit choke proven adversarially (`1198dce` on origin).

## Refs
`WO-P2-OPS-VERB-G-PREP.md` G2 · `canon/doctrine/action-safety-guards.md` · Max GO @ 13:15:00Z (G2→G3→G4) · hub Accept `1198dce` on origin `ae95271`
