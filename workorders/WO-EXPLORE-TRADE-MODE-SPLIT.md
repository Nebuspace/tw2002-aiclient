# WO-EXPLORE-TRADE-MODE-SPLIT

**Goal:** Align Play with `RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES` (Max ratify 2026-08-01): Explore discovers; `L` arms a loop; `T` executes it; `P` money-gates execution only.

**Refs:** `canon/DECISIONS.md` RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES · `canon/surfaces/mode-line-and-teach-controls.md`

## Scope

### A — Decouple Explore gather from Port Trade
- `dock_new_ports` for Explore = **True** (discovery sampling), **not** `play.port_trade_on`.
- All `_start_policy_explore` / App-armed explore / `E` paths stop reading Port Trade for dock.

### B — Stop FOCUS silent trade auto-fire
- `_autonomy_auto_fire` must **not** start `run_chain` from FOCUS bubble.
- Keep Cargo Hold Upgrade auto-fire.
- Remove / neutralize `_prefer_explore_while_trade_blocked` trade→explore kick used only for that path (or leave harmless if unused).

### C — `L` arms · `T` executes
- `T` calm key → `trade_loop_toggle` (retire calm-path `assign_trigger` for `T`).
- Persist L-armed selection on Play (`trade_loop_arm`: discovered plan fingerprint+world_id **or** taught loop name).
- Enter in `L` modal **arms** selection (status: armed route / name — press T to run); under APP-ARMED may skip `y` for arm-only (execution is T).
- `T`: if trade/autoloop running for that arm → stop; else if `P` OFF → refuse; else if nothing armed → refuse “select with L”; else start `trade_chain_start` (discovered) or `autoloop_start` (taught).
- Soft: allow selecting discovered rows even when search is **PARTIAL** (show banner; do not hide all chains).
- Soft: `discovery_blocks_start` only when truncated **and** no chains (exact fingerprint still in partial list may start).

### D — Canon
- DECISIONS + mode-line already amended on this branch.

## Out of bounds
- #308 death-respawn
- Rewrite of explore DFS budget (optional follow-up)
- Ship Upgrade engine

## Accept
1. Pins: Port Trade OFF still explores with dock gather; Port Trade ON does not FOCUS-auto-start trade.
2. Pins: `T` returns trade_loop intent; assign_trigger not on calm `T`.
3. Pins: L-select under partial discovery selectable; truncated+empty still blocks start; truncated+matched fingerprint starts.
4. Suite green.
5. Live: NOT-ATTEMPTED OK if offline Accept met; hub may prove L→T run separately.

## Proof
suite + pins. No self-merge.
