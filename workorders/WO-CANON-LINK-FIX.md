# WO-CANON-LINK-FIX — Repair 8 broken canon markdown links + pin

**Status:** DONE · origin `3a48c04` (#181) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-28 · hub  
**Refs:** PROCESS-NOTE 2026-07-28T17:28:18Z (8 broken `](/…md)` links)

## Goal
1. Fix the three link faults (8 occurrences):
   - `/app-autopilot-model.md` → `/architecture/app-autopilot-model.md` (2× `engine/macros.md`)
   - `/engine/action-safety-guards.md` → `/doctrine/action-safety-guards.md` (3×)
   - `/surfaces/trainer-ui.md` → `/surfaces/trainer-cockpit.md` (3× `architecture/cli-verbs.md`)
2. Add a **canon link-check test** resolving every `](/…md)` against the tree, with a **positive control** so an empty matcher cannot pass as clean.
3. Suite green; live-prove `n/a` (docs/test hygiene).

## Out of bounds
Not on #177. No product code. No sw2102-docs public push.
