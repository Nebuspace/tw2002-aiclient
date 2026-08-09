---
type: Research
status: Partial — StarDock reached; fighter unit-price screen not found
date: 2026-08-09
---

# Fighters / cargo / ship purchase coverage (live, 2026-08-09)

## Scope

Sacrificial `scout_academy` follow-on to
[autopilot-live-drive-findings-2026-08-08](/research/autopilot-live-drive-findings-2026-08-08.md)
Axes 3–4 and
[stardock-ship-purchase-capture-2026-08-08](/research/stardock-ship-purchase-capture-2026-08-08.md).
Goal: reach StarDock, capture a **real Class-0 / StarDock fighter unit price**
(for the two 100cr placeholders), and note cargo-hold / ship-purchase screen
coverage. Read-only intent for price capture (back out — no buy EXECUTE).

## What was exercised live

1. **StarDock location confirmed.** `?` help → sector re-display at sector
   **8039** shows `Ports : Stargate Alpha I, Class 9 (Special) (StarDock)` with
   FedSpace beacon. Matches the prior research `V`-status disclosure of 8039.
2. **`P` dock still lands ordinary commodity commerce** (Fuel Ore / Organics /
   Equipment buy/sell / "nothing they want") — same shape as
   stardock-ship-purchase-capture, Class 9 Special, not a Hardware/Ordnance
   storefront.
3. **Onboard Computer (`C`) help** lists ship catalog / port report / etc. —
   no "buy fighters" entry. Ship catalog path remains the read-only browser
   already documented (no purchase confirm).
4. **Top-level `?` help** at 8039 — no Ship Dealer / Upgrade Ship / Buy
   Fighters letter (same exhaustive gap as the ship-purchase capture).
5. **`find_stardock` explore** (turn_budget 80) halted
   `explore_exhausted:turn_budget` with **zero** `landmarks` written — World
   Model still has no `StarDock` landmark for this world after the run
   (operator navigation used the known 8039 fact instead).

## Fighter unit price

**Not captured.** No live screen quoting credits-per-fighter was reached on
this server in this pass. Therefore:

- Tip `FIGHTER_UNIT_PRICE_DEFAULT = 100` in
  `session/explore_defensive_posture.py` stays a **placeholder**.
- Canon hypothesis `FIGHTER_UNIT_PRICE_CLASS0 = 100 cr/fighter` stays
  **UNVERIFIED** ([priority-engine](/engine/priority-engine.md)).
- `afford_fighters()` correctly remains injection-only (`fighter_unit_price` /
  `fighter_price_class0`) — do **not** promote 100cr to a measured constant
  from this pass.

## Cargo holds / ship purchase

**Unchanged gaps** relative to stardock-ship-purchase-capture-2026-08-08:

- No live `stardock_cargo_hold_quote` / shipyard-registration purchase-confirm
  path reproduced (`s`/`S` remains Long Range Scan on this TWGS).
- Fixture-backed parsers stay ahead of this server's exposed menus.

## Implications

| Queue item | This pass |
|---|---|
| `WO-BUILD-FIGHTER-CLASS0-LIVE-PRICE-CAPTURE` | **Not closed** — StarDock reached; price screen absent / not found. Keep placeholders; no constant flip. |
| `WO-RESEARCH-FIGHTERS-CARGO-SHIP-PURCHASE-COVERAGE` | **Closed as research** — coverage documented; purchase surfaces still missing on this host. |
| Buy EXECUTE / purchase drivers | Still blocked on ground-truth screens (unchanged). |

## Non-goals / hygiene

- Real accounts untouched; profile `scout_academy` only.
- World slug and operator-home paths omitted from committed evidence.
- Credits moved during unrelated trade-chain / session noise this session are
  **not** fighter purchases (fighters_aboard stayed 99 across the StarDock
  visit).
