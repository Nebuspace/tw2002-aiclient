# WO-LIVE-WITNESS-FIRST-TRADE-LOOP

**Parent:** `WO-ESCALATE-LIVE-DRIVE-DOUBLE-MONEY-FINDINGS`

**Status:** **LIVE WITNESS RUN 2026-08-07** — explore half PROVED; trade-arm BLOCKED by hop-cap truncation.

## Goal

Re-run the sacrificial live drive after `#509` (`tw chain`) + `#510` (StarDock
skip): explore past sector-1 Class 0, discover priced routes, arm via
`tw chain start --fingerprint`, observe credit delta.

## What ran (disposable / `crawl_sacrificial=true`)

1. `tw ensure --profile <sacrificial>` → main_command; credits **99000**, turns ~30409, sector 1 Class 0 Special.
2. `tw explore start --world-id <world> --turn-budget 300 --dock-new-ports --min-sectors 0`
   - **Did NOT** halt on `dock_report_unreadable` (regression vs pre-#510 live drive).
   - Outcome: `halted` / `explore_exhausted:turn_budget`
   - distinct_sectors **130**, sends_issued **481**, finished cleanly.
3. World-model after explore: ~123+ sector files; **~72** ports with commodities; `tw pairs` → **495** pairs.
4. Default `tw chains --json` → `chains: []`, `reason: no_closed_cycle`,
   `truncated: true`, adapter_note `capped at 500 hops (1554 candidates from 4992 compatible pairs)`.
5. Raised-cap offline recompute (`TradeAdapterConfig(max_hops=5000)`,
   `max_search_steps=500_000`) → **19484** cycles (search still partial on starts).
6. `tw chain start --fingerprint <64-hex from raised-cap top cycle>` →
   **`{"ok": false, "error": "chain_discovery_partial"}`**
   (daemon `recompute` still uses default `max_hops=500` → truncated empty →
   `discovery_blocks_start`).
7. Credits after attempt: **99000** (unchanged). Daemon stopped.

## Verdict

- **#510 StarDock skip: PROVED live** — explore survives Class 0 and prices commodity ports.
- **Double-money arm: NOT YET** — not a missing CLI verb; discovery hop-cap
  (`trade_adapter.DEFAULT_MAX_HOPS=500`) makes default `chain_search.recompute`
  (and therefore `trade_chain.start`) refuse with `chain_discovery_partial`
  on this denser post-explore map. Mid-explore, a smaller hop set briefly
  listed cycles under truncation; after full map growth, top-500 edges
  contain no closed cycle.

## Follow-on (scoped)

- **WO-FIX-TRADE-ADAPTER-HOP-CAP-FOR-CHAIN-ARM** — raise or make configurable
  the adapter hop budget used by `session/trade_chain.start`'s discovery
  (mirrors the existing `max_search_steps=500_000` deepen), so an exact
  fingerprint from a viable discovery can resolve without false
  `chain_discovery_partial`. Re-run this witness WO after.

## Accept (this WO)

1. Live explore past Class 0 without `dock_report_unreadable` — **met**.
2. Credits before/after + blocker named honestly — **met** (99000→99000,
   blocker = hop-cap / `chain_discovery_partial`).
3. Double-money proof — **deferred** to hop-cap follow-on + re-run.

## Refs

Parent findings; `#509`; `#510`; `trade_adapter.DEFAULT_MAX_HOPS`;
`session/trade_chain.discovery_blocks_start`; hub HANDOFF 2026-08-07T06:07Z
(standing carte-blanche disposable arm).
