# WO-CANON-FIX-SHIP-PROGRESSION-STALE-STATUS-PRODUCER-GAP

**Status:** DONE (this PR) · gated: no (docs-only)
**Posted:** 2026-08-08 · self-seed from HANDOFF 14:37 MED clear · queue-aiclient ~352

## Goal

Remove the stale "Still missing: status producers…" claim from
`canon/strategy/ship-progression.md` Code divergence. `merge_upgrade_status_inputs` has been
live on tip since PR #526 (`7fb66651`) via `GameDataStats.merge` (catalog/player/hold cost)
and `FocusScalars.merge` (priced-chain `upgrade_loop`).

## Scope

`canon/strategy/ship-progression.md` only — rewrite the first Code-divergence bullet to
present-tense LIVE producers + fail-closed omission when evidence is incomplete.

## Constraints

- Docs-only. No product-code changes.
- Do not claim coach always has a decision — incomplete catalog/chain still returns `None`.
- Keep the TW-22 / auto-max-holds divergence bullet unchanged.

## Accept

- Canon no longer says status producers are missing.
- Bullet cites `merge_upgrade_status_inputs` / PR #526 / `GameDataStats` + `FocusScalars`.
- Diff limited to that one bullet (plus this WO file).

## Proof

Docs-only. live-prove: **n/a**.

## Refs

- queue-aiclient.md ~352 · vs tip `game_data_stats.py` (~152) · `focus_status.py` FocusScalars.merge
- PR #526 merge `7fb66651` · `ship_upgrade_decision.merge_upgrade_status_inputs`
- HANDOFF 2026-08-08T14:37:00Z MED clear preference
