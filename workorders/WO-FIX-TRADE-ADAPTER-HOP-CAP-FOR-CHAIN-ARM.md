# WO-FIX-TRADE-ADAPTER-HOP-CAP-FOR-CHAIN-ARM

**Parent:** `WO-LIVE-WITNESS-FIRST-TRADE-LOOP` (orchestrator live-witness run, 2026-08-07) —
`WO-ESCALATE-LIVE-DRIVE-DOUBLE-MONEY-FINDINGS` chain.

## What the live witness found

With `WO-FIX-EXPLORE-SKIP-SPECIAL-PORTS` (#510) live-proved — explore now gets past a Class 0
StarDock and fully maps a world (130 distinct sectors, 481 sends, no `dock_report_unreadable`
halt) — the run hit a new, different blocker at the arm step:

- `tw chains` with the default adapter settings returns empty/truncated: `trade_adapter.py`'s
  `DEFAULT_MAX_HOPS = 500` (line 105) caps edge output before a real cycle set can be built —
  1554 candidate hops truncated from 4992 real pairs.
- An offline recompute with a raised cap (`max_hops=5000`, `max_search_steps=500000`) found
  19,484 cycles from the same discovered world — the data is there, the adapter's default is
  just too conservative for a fully-mapped 130-sector world.
- `tw chain start --fingerprint <top-ranked>` then fails with `chain_discovery_partial` →
  `discovery_blocks_start`, because the **daemon's own discovery path still uses the
  `DEFAULT_MAX_HOPS=500` default**, independent of the offline recompute.

## Goal

Raise (or make configurable) the daemon-side trade-chain discovery hop-cap so `tw chain start`
can actually arm on a fully-explored world, without regressing the "bounded compute/output on a
large known map" intent the constant's own comment documents.

## Scope

- `tw2002_aiclient/trade_adapter.py` — `DEFAULT_MAX_HOPS` (and `max_search_steps` if the same
  bound applies at the daemon layer, not just the offline recompute path used to diagnose this).
- `tw2002_aiclient/chains.py` — confirm callers pick up the new default; its own module comment
  already distinguishes "ADAPTER's edge output" bound from other bounds — read that context
  before changing anything nearby.
- `tw2002_aiclient/session/trade_chain.py` / `session/protocol.py`'s `trade_chain_start` RPC path
  — wherever daemon-side discovery invokes the adapter, confirm it isn't pinned to the old
  default via a separate constant.

## Out of scope

- Changing `port_needs_dock` / explore behavior (already fixed, #510).
- A configurable-per-world hop-cap UI/CLI flag — pick one raised default first; only add a flag
  if a single default can't serve both small and large worlds.
- The actual re-run proving credits double — that's the rest of
  `WO-LIVE-WITNESS-FIRST-TRADE-LOOP`, blocked on this landing first.

## Constraints

- Ungated, buildable now — this is a tuning-constant fix, not a new dependency or
  safety-list item (verified: `DEFAULT_MAX_HOPS = 500` is a plain module-level int in
  `trade_adapter.py:105`, not config/secrets-adjacent).
- Don't just blindly bump to whatever number happened to work in the one-off offline recompute
  (5000/500000) — pick a bound with a stated rationale (e.g. proportional to discovered sector
  count) so it doesn't just move the same wall further out on a bigger world.

## Accept

1. On the same academy_of_tradewars-shaped fully-explored world data, `tw chains` (default
   settings, no manual override) returns a non-empty, non-`chain_discovery_partial` candidate
   set.
2. `tw chain start --fingerprint <a-real-candidate>` arms successfully (no
   `discovery_blocks_start`).
3. Existing hop-cap-related tests (if any pin `DEFAULT_MAX_HOPS=500`) updated to the new value
   with a comment explaining the change, not silently bumped.

## Proof

Offline: `pytest` on `trade_adapter.py`/`chains.py` coverage. Live: re-run the arm step of
`WO-LIVE-WITNESS-FIRST-TRADE-LOOP` on a sacrificial profile (already carte-blanche authorized)
and confirm `tw chain start` succeeds — this closes the loop back to the parent WO.

## Owner

tw2002-aiclient — `tw2002_aiclient/trade_adapter.py`, `tw2002_aiclient/chains.py`,
`tw2002_aiclient/session/trade_chain.py`.
