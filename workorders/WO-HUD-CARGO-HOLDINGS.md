# WO-HUD-CARGO-HOLDINGS

**Status:** READY · EXECUTE · HIGH · Max ask · Cursor  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/HUD-CARGO-HOLDINGS`  
**Depends:** `main` ≥ `9b78c57` (#305 empty/total)  
**Plan:** `.samantha/plans/trade-loop-cargo-hud.md` wave 2

## Why

#305 paints `M empty / N`. Max still wants to know **what** fills the other holds (Fuel Ore / Organics / Equipment). Trade driver already knows `held_qty` + commodity per hop after buy; nothing sticks to the HUD.

## Goal

Sticky **holdings** (ore / organics / equipment) on the session → HUD shows them with the occupancy string (e.g. `10 empty / 60 · Equ 50` or compact sublines if the right gutter already allows without layout thrash).

## Scope

1. **Model:** Session sticky holdings `{fuel_ore, organics, equipment}` (ints ≥0). Clear/reset policy: unknown until first verified write; never invent from port **market** rows.
2. **Writers:** After successful trade_driver buy/sell for a hop commodity, update holdings (buy += qty, sell −= qty, clamp ≥0). Prefer a small session API (`observe_holdings` / `set_holdings`) called from the driver or trade_chain progress path — keep layering clean.
3. **Optional parse:** If ship-info ever prints per-commodity hold lines in fixtures/live, parse into sticky; if no fixture shape yet, skip parse and document.
4. **HUD:** Extend `format_cargo_hud_value` (or sibling) to include non-zero holdings in the CARGO cell (width-safe; clip honestly). Pins for buy→Equ sticky → HUD string; sell clears; market rows still non-write.
5. This WO on the branch. Touch canon blurb only if holdings display needs a one-line cite (DECISION already Pending).

## Out of scope

Hop LOGS / status_line (→ **WO-TRADE-LOOP-HOP-VISIBLE**) · haggle · changing empty/total arithmetic from #305.

## Accept

1. After a simulated/pinned buy of Equipment N, HUD CARGO mentions Equ N (with empty/total still honest).
2. Sell reduces/clears that holding; no market-row invention.
3. Focused pins + full suite green; live-prove **n/a** unless seat touches live start verbs (prefer n/a).

## Proof

pytest + STATUS. No self-merge.

## Refs

`trade_driver.py` held_qty · `hud_tracking.format_cargo_hud_value` · plan trade-loop-cargo-hud wave 2
