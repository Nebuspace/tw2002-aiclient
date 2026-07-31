# WO-DEC-07-WO-ATOMIC

**Goal:** Enforce that work-order markdown is committed on the hub-seeded
branch **before** HANDOFF — mechanically, not by habit.

## Why

Coord rule already requires `workorders/WO-<ID>.md` on the branch before
HANDOFF. Misses still happen (WO left untracked on hub tree only). Wire a
pre-handoff / pre-push check so the ritual cannot skip the artifact.

## Fix

1. Script (or extend `coordination-precommit-hook.sh` / hub seed helper):
   given branch `wo/<ID>`, require `workorders/WO-<ID>.md` (or
   `workorders/WO-<slug>.md` matching branch) present in `HEAD`.
2. Document one-liner in hub merge/HANDOFF checklist.
3. Offline pin: fixture branch without WO → script exits non-zero; with WO → 0.

## Accept

1. Script refuses missing WO path on a `wo/*` tip.
2. Script accepts when WO file is in HEAD.
3. No new runtime deps; live-prove **n/a** (process/CI helper).

## Scope

- `scripts/` helper (+ optional pre-push/hook wire)
- short note in existing WO-PR ritual doc or `workorders/README` if present
- `workorders/WO-DEC-07-WO-ATOMIC.md`
- tests for the script

## Constraints

- Additive · no force-push · no secrets
- Does not change product code

## Proof

Offline script pins. live-prove **n/a**.

## Refs

- `.cursor/rules/workorders-required.mdc`
- `WO-PR-CI-LIVE-PROVE-SPLIT.md` hub seed ritual
