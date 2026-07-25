# WO-P2-G3-LOOPS — tw loops list (store read, empty-honest)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **IN FLIGHT** 2026-07-25 · engine committed local **`31c871f`** (CC; Push waits Accept) · CLI wire pending `cli.py` ownership after SURROGATE-ASCII
> Type: build · Phase: 2 · Seat: impl-claudecode-aiclient (Fable)
> Refs: `WO-P2-OPS-VERB-G-PREP.md` G3 · `canon/engine/macros.md` · ULTRACODE-WO-INVENTORY.md Phase 2

## Goal
`tw loops` list — protocol + CLI; **empty-honest OK** if store thin. Honest empty ≠ fake rows. Store is a directory of independent macro/loop documents; partial listing OK (unlike player_bank's single-file all-or-nothing). Schema from `macros.md` + `candidate-mining.md` + `world-identity.md`. `loops` stays off `./tw --help` until this WO Accepts.

## Scope
- `tw2002_aiclient/` loops list surface (store read + protocol verb if needed + CLI)
- `tests/` — proving tests (empty / non-empty / unreadable distinction)
- Allowlist + README update when CLI wired

## Constraints
- `loops` stays off `./tw --help` until this WO Accepts (honesty bar)
- No G4/`loop_player`/autoloop yet; no crawl_sacrificial enable
- Announce if CLI touches `cli.py` while Cursor product wave is live
- Push waits Accept; G4 serialized behind G3 Accept

## Accept
1. Empty store prints honest empty (not "no loops" when unreadable)
2. Non-empty lists real rows only (no invented rows)
3. `./tw --help` unchanged until Accept
4. Tests green

## Proof
Unit (+ pty/CLI if CLI wired) + STATUS with SHA.  
Engine: `31c871f` (local; 30/30 green, evaluator-run). CLI wire: pending `cli.py` owner after SURROGATE-ASCII.

## Refs
`WO-P2-OPS-VERB-G-PREP.md` G3 · `macros.md` schema · Max GO G2→G3→G4 @ 13:15:00Z · hub HANDOFF @ 14:02:06Z
