# WO-AI-TRANCHE-6-DOCS-A

**Status:** DONE (docs batch)
**Branch:** `wo/AI-TRANCHE-6-DOCS-A`
**Gated:** no (docs-only)

## Goal

Close four canon/doc honesty gaps from the AI tranche-6 docs batch — no code behavior changes.

## Scope

1. `canon/architecture/cli-verbs.md` — `players {list,next,rotate}` LIVE (match `players_cli.py`).
2. `canon/DECISIONS.md` — RESOLVED empty/total CARGO (#305); ship-info holdings parse stays OPEN.
3. `canon/strategy/ship-progression.md` + `canon/doctrine/action-safety-guards.md` — App-armed Cargo·ON auto-fire carve-out (RESOLVED-TRAINER-STRIP point 6).
4. `canon/DECISIONS.md` + `canon/engine/auto-haggle.md` — haggle defaults registry DONE (#575).

## Accept

All four items land; path-leak scan clean; PR ready for review.

## Proof

`scripts/path-leak-scan.sh` on staged paths; diff review only (no product suite required for docs-only).
