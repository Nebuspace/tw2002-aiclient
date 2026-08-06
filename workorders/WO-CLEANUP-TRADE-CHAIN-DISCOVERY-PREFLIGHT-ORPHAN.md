# WO-CLEANUP-TRADE-CHAIN-DISCOVERY-PREFLIGHT-ORPHAN — delete dead client preflight

**Status:** IN FLIGHT · Cursor · `wo/CLEANUP-TRADE-CHAIN-DISCOVERY-PREFLIGHT-ORPHAN`  
**Posted:** Cycle-43 MED · queue-aiclient.md

## Goal

Dispose `app._trade_chain_discovery_preflight` — zero product callers after
FOCUS `run_chain` auto-fire retirement. Daemon-side
`trade_chain.discovery_blocks_start` remains the live refuse gate.

## Accept

1. Helper gone; no product/test references except historical WO docs.
2. Auto-fire dead pin still green without monkeypatching the helper.
3. live-prove `n/a` (dead scaffolding; money-path refuse unchanged daemon-side).

## Refs

- `app.py` (removed) · `session/trade_chain.py::discovery_blocks_start`
- Prior intent: `workorders/WO-TRADE-PARTIAL-BACKOFF.md` (DONE; auto-fire path gone)
