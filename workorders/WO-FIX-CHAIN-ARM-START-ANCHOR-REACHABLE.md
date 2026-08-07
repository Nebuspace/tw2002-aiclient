# WO-FIX-CHAIN-ARM-START-ANCHOR-REACHABLE

**Parent:** `WO-LIVE-WITNESS-FIRST-TRADE-LOOP` / hop-cap #511 residual
(orchestrator ACK 2026-08-07T06:23Z).

## What the live witness found

After #511, `tw chain start` arms successfully (`started: true`, no
`chain_discovery_partial`). The run then halted immediately with
`start_anchor_mismatch:<here>:<anchor>`:

- Ship was in sector **6461** after explore.
- Every ranked cycle on that world started at **882**.
- **Undirected** known-graph connectivity: 6461 ↔ 882 ↔ FedSpace (sector 1).
- **Directed** outbound BFS from 6461: 95-sector sink; **cannot** warp to 882
  or sector 1 (warps are one-way in the stored graph).

So hop-cap is fixed; the remaining double-money blocker is **arming while
not at (and unable to reach) the chain start_anchor**.

## Goal

Fail closed *before* arming when the current sector has no directed path to
the chain's start_anchor, with a typed reason operators can act on — and
document the live recovery path (re-seat at FedSpace / travel while a path
exists) so the parent witness can finish.

## Scope

- `tw2002_aiclient/session/trade_chain.py` (and/or `trade_driver.py`) —
  preflight directed reachability from current sector → `plan.start_anchor`
  using the same known-graph the adapter uses; refuse with a stable reason
  (e.g. `start_anchor_unreachable`) instead of starting a zero-send run that
  immediately mismatches.
- Tests for reachable / unreachable / already-at-anchor.
- This WO file; brief pointer from `WO-LIVE-WITNESS-FIRST-TRADE-LOOP.md`.

## Out of scope

- Automatic multi-hop travel / twarp / FedSpace transporter automation
  (separate WO if needed after this fail-closed gate ships).
- Changing hop-cap / discovery (#511 done).
- Inventing undirected warps (game is directed).

## Constraints

- Ungated (session/trade logic, no new deps, not secrets-adjacent).
- AI never live-drives; any future auto-travel would still be `{app}` under
  control-lock after human arm — not this WO.
- Public-repo: no FQDNs/handles in WO proof prose.

## Accept

1. When current sector cannot directed-reach `start_anchor`, `trade_chain_start`
   / `tw chain start` refuses with a typed unreachable reason (does not
   publish `started: true` then halt on mismatch with 0 sends).
2. When already at `start_anchor` (or a directed path exists — if this WO
   only gates unreachable, path-exists may still defer travel to the driver),
   existing arm path still works.
3. Offline pins green; live residual for parent witness: arm from a sector
   that can reach the cycle (FedSpace / start_anchor), then observe credits.

## Proof

`pytest` on the new preflight pins. Live: sacrificial re-arm from a
reachable seat (FedSpace or 882) after this lands — closes parent
`WO-LIVE-WITNESS-FIRST-TRADE-LOOP` credit half.

## Owner

tw2002-aiclient — `session/trade_chain.py`, `trade_driver.py`.
