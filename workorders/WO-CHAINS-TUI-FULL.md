# WO-CHAINS-TUI-FULL — Full Trade-Loop-Chains library modal (`L)chains`)

**Status:** DONE · origin `95fc4af` (#147) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-27T21:35Z staged · EXEC overnight after #144 N-port wire  
**Depends:** #144 `tw chains` / chain_search on main · taught path already present  
**Refs:** wire-class W4 · mode-line-and-teach-controls · visual-language · trainer-cockpit  
**Model:** Fable (Phase 3–5 UI standing rule)

## Goal
Operator-visible automation: `L)chains` modal shows **discovered** N-port/profit chains (from
`chain_search` / same producer as `tw chains`) **and** taught loops; select → confirm-gate → arm.

## Accept
1. `L` opens modal; dismiss without arm.
2. Discovered rows: sectors / cr/turn / hops (or honest empty + truncation honesty from #144).
3. Taught rows from loop store (existing path OK).
4. Select + confirm arms (`autoloop_start` or equivalent); bare Enter never fires.
5. Explore `E` unchanged.
6. Suite + STATUS. live-prove: safe half OK; turn-spend arm NOT-ATTEMPTED.

## Constraints
Money-path confirm-gate non-negotiable. No EV finder in modal. Do not regress #144 CLI.
Explicit paths. Public-repo safe. `cli.py` line-cap split = separate bank, not this DoD.
