# WO-EXPLORE-GATHER-VISIBLE — make port commodity investigation unmistakable

**Status:** DONE · origin `8f4e6fc` (#227) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/EXPLORE-GATHER-VISIBLE`
**Depends:** `main` ≥ `833c83c` (#226 HUD bridge)

## Goal

Operators exploring the map stop warping past ports without realizing
commodity investigation is opt-in. Dock+ingest already exists
(`sector_explore.dock_new_ports` / `_dock_and_ingest`); Play has `D` then `E`
(WO-PLAY-EXPLORE-FLAGS), but Max live-testing saw ports and no commodity stops
— Gather is too easy to miss.

## Symptom (operator)

Explore warps across sectors showing ports; does not stop to investigate
commodities. Root cause when only `E`/`y` pressed: `dock_new_ports` default
**False** (WO-EXPLORE-DOCK-DEFAULT-OFF) by design after dialect scar.

## Scope

1. **Make Gather unmistakable in Play chrome** before Explore starts:
   - Status / confirm / band must show dock+ingest state without hunting
     (`+dock` / dock OFF wording already partially present — raise visibility
     so Ada would not miss it in three seconds).
   - Confirm line for Explore must continue to include `+dock` when opt-in is
     ON (regression pin).

2. **Optional but preferred:** a one-shot **Gather** explore intent (key or
   labeled confirm path) that starts with dock ON after explicit confirm —
   operator still confirms; no silent auto-start.

3. **Do not silently flip** the CLI / library `dock_new_ports` default to ON
   without Max GO (dialect scar memory / WO-EXPLORE-DOCK-DEFAULT-OFF). Play
   discoverability is the fix; default-ON is a separate Max gate.

4. Offline pins: chrome/confirm text shows dock state; explore with dock ON
   still docks+ingests (existing path); dock OFF still skips (regression).

## Out of scope

- Flipping CLI/library default dock ON (Max GO required).
- Chains live refresh (next WO — needs commodity-rich world model).
- HUD vitals (#226 done).
- Cycles / armed-run widening.
- `#218` app.py split (frozen).

## Constraints

- Smallest change that makes Gather impossible to miss in Play.
- No new money path / no auto-trade; dock+ingest only.
- Live-prove → Cursor after suite: Explore with Gather/dock ON on ≥1 host;
  observe a dock/commodity ingest (or honest skip with reason if host has no
  new ports). Safe half.

## Accept

1. Play UI makes dock+ingest state obvious before Explore confirm (status and
   confirm both; no "secret `D` only").
2. With Gather/dock ON + confirm, explore still docks new ports and ingests
   commodities into the world model (offline fixture proof).
3. With dock OFF, explore still skips dock (regression — default-OFF holds).
4. CLI library default remains OFF unless Max separately GOs a default flip.
5. Full offline `suite` green.

## Proof

- Focused Play chrome / confirm / explore_flags tests.
- Existing dock+ingest tests stay green; add visibility pins as needed.
- Full offline `suite`.
- **Live: DEFERRED → Cursor** after suite.

## Refs

- Max live-test 2026-07-29 (ports visible, no commodity stops)
- `.samantha/plans/visible-client-gaps-2026-07-29.md`
- `cockpit/explore_flags.py` · `app.py` Explore/`D` path
- `session/sector_explore.py` `_dock_and_ingest`
- WO-EXPLORE-DOCK-DEFAULT-OFF · WO-PLAY-EXPLORE-FLAGS · WO-EXPLORE-DOCK-DIALECT
