# WO-CANON-FIX-EXPLORATION-POLICY-STALE-4-INTENT-CYCLE

**Status:** READY · gated: no (docs-only) · **re-scoped** 2026-08-10 (hub correction)
**Posted:** 2026-08-10 · Cycle-49 audit HOLD → re-scope after #666

## Goal (re-scoped — do NOT use the original audit premise)

Tip-true the arming-surface prose in `canon/strategy/exploration-policy.md`.

**Original audit premise was WRONG:** it claimed `chain_hunt` had zero implementation.
Chain-hunt already shipped in PR `#640` / `#641` (`plan_chain_hunt` / `INTENT_CHAIN_HUNT` /
CLI + daemon wiring). Canon planner prose was already tip-true'd in `#641`.

**Real residual (hub re-scope):** Schema ~lines 64–65 still described a trainer-panel cycle
`off → mapfill → stardock → formations → chainhunt → off` and called Panel/CLI wiring for
`chainhunt` a "follow-on build," even though:

- Play E-cycle is **2-wide** (`ARMABLE_INTENTS` = `map_fill`, `find_stardock`; `#247` /
  WO-RETIRE-CYCLE-EXPLORE-MODE)
- `chain_hunt` (and `find_formations`) are **CLI/daemon-armable and LIVE** after `#640`/`#641`

## Scope

`canon/strategy/exploration-policy.md` only:

1. **Schema** — replace the stale panel-cycle / "follow-on build" paragraph with tip-true
   arming-surface prose (2-wide Play toggle + CLI-live `chain_hunt` / `find_formations`).
2. **Code divergence** — record the closed stale claim so it is not re-litigated as
   "chain_hunt unbuilt" or as a 4-/5-step panel cycle.

Optional companion: this WO markdown under `workorders/`.

## Constraints

- Docs-only. No product code.
- Do **not** claim chain_hunt is unbuilt.
- Do **not** invent a panel cycle tip does not have.
- Do **not** touch Max-gated `WO-ESCALATE-BOUNDED-REPEAT-*`.

## Accept

- Schema no longer asserts the multi-step panel cycle or "follow-on" CLI wiring for chainhunt.
- Schema states Play is 2-wide and `chain_hunt` / `find_formations` are CLI-live.
- Code divergence names the closed stale claim with `#640`/`#641` / `#247` anchors.
- Diff limited to exploration-policy (+ this WO file).

## Proof

`git show` / diff of `canon/strategy/exploration-policy.md`. Docs-only — no suite implication.
Verify-first cite: `origin/main:canon/strategy/exploration-policy.md` lines 63–66 (pre-fix).

## Refs

- Hub STATUS-ACK 2026-08-10T04:57:54Z (premise correction + HOLD re-scope)
- `tw2002_aiclient/explore.py` — `ARMABLE_INTENTS`, `INTENTS`, `INTENT_CHAIN_HUNT`, `plan_chain_hunt`
- `tw2002_aiclient/session/cli.py` — `--intent` choices / chain_hunt help (not on Play E cycle)
- PR `#640` / `#641` (chain_hunt ship) · `#247` (2-wide Play E)
