# WO-CHAIN-NPORT-WIRE — Wire N-port `chains.py` finder to a product surface

**Status:** DONE · origin `23d9874` (#144) · Accept verified 2026-07-28 (ship tests green on tip)
**Posted:** 2026-07-28T03:23Z bank · EXEC seeded after #142 · overnight carte blanche  
**Refs:** wire-class W2/W3 · #128 pairs already wired · #142 import hygiene on main

## Goal
Put the **already-built** N-port finder on a real product path so automation is *visible*:
`trade_adapter.build_trade_hops` → `chains.find_profit_chains` / `rank_chains` / `longest_profit_chain`
→ operator-facing surface.

## Hub ruling (do not re-ask)
**Wire — do not retire.** Prefer thin CLI first (`tw chains` or extend `tw pairs` sibling) that
prints ranked N-port chains (or honest empty + reason). Play/`L)chains` discovered rows = follow-on
`WO-CHAINS-TUI-FULL` (do not block this WO on full TUI).

## Accept
1. ≥1 non-test product caller reaches `find_profit_chains` (or `longest_profit_chain`) with hops from
   `build_trade_hops` (or documented equivalent producer).
2. Pin: empty world / no hops → honest empty, not crash; budget note surfaces if truncation fires.
3. **Before trusting the wire:** run `tests/test_import_hygiene.py` green; check ignored/skipped tests
   covering chains/trade_adapter (same trap as formations landmine) — un-skip or add collected pin.
4. Suite + STATUS. live-prove: safe half OK under hub GO (read-only recompute on a world with ports);
   turn-spend arm = NOT-ATTEMPTED this WO.
5. Do not conflate with #128 pair loops or taught `L)chains` macros.

## Constraints
Owned: `tw2002_aiclient/chains.py` · `trade_adapter.py` · `chain_detect*.py` if composing ·
`session/cli.py` · tests. Coordinate file lanes. Public-repo safe. Explicit paths only.
