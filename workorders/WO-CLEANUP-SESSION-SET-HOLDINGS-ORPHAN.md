# WO-CLEANUP-SESSION-SET-HOLDINGS-ORPHAN — remove unused Session.set_holdings

**Status:** IN FLIGHT · Cursor · `wo/CLEANUP-SESSION-SET-HOLDINGS-ORPHAN`  
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Delete `Session.set_holdings` — zero product/test callers; live paths are
`adjust_holdings` / `observe_holdings` / `observe_cargo`. Drop the stale
`trainer-cockpit.md` citation.

## Accept

1. `set_holdings` gone from `session/session.py`.
2. Canon citation updated.
3. live-prove `n/a` (dead-API cleanup).

## Refs

- Cycle-43 · `session/session.py` (was ~660)
