---
type: Research
status: Gap found — no purchase-confirm ground truth captured
date: 2026-08-08
---

# StarDock ship-purchase live-capture attempt (2026-08-08)

## Scope

Live-drive capture pass on the `scout_academy` sacrificial profile (`crawl_sacrificial = true`),
purely to find the actual StarDock ship-**purchase** keystroke/confirm flow, ahead of building
`WO-BUILD-STARDOCK-SHIP-PURCHASE-DRIVER`. Baseline: 97,809 credits, sector 22673, Mammongam Scout
Marauder, 99 fighters. No credits were spent during this pass (final balance unchanged).

## What was found live

- `V` (View Game Status) discloses the world's StarDock sector directly: sector 8039.
- `M` then the sector number computes a shortest path and offers `Engage the Autopilot? (Y/N/...)`;
  autopilot ran the route and stopped correctly at 8039.
- `P` while in-sector at StarDock docks (`<T> Trade at this Port` / `<Q> Quit, nevermind`) and lands
  directly in ordinary commodity commerce (Fuel Ore / Organics / Equipment buy/sell prompts) —
  identical shape to any other port, just Class 9.
- `C` (Onboard Computer) → `C` (View Ship Catalog) reaches a **read-only** spec browser: pick a
  letter (`A`-`R`), see that ship's stats (holds/fighters/shields/cost/etc. — confirmed present,
  though the live 25-row terminal scrolls the header off screen before it can be captured whole),
  then the same selection prompt returns. The catalog's own text says "browse through Starship
  specs" — nothing in this menu asks "Buy this ship (Y/N)?" or deducts credits.
- `T` (Corporate Menu) opens a "Corp Menu" / "Corporate command" prompt with no listed sub-options
  reachable this session (no corporation owned).
- `L` (Land on a Planet) at sector 8039 correctly refuses — "There isn't a planet in this sector."
- Exhaustively checked every letter in the top-level `?` help menu at StarDock — no `Ship Dealer` /
  `Upgrade Ship` / `Buy New Ship` entry exists anywhere in it.

## The gap

**No purchase-confirm prompt was reached on this live server.** The repo already carries a
`tests/fixtures/stardock_shipyard_listing.txt` fixture (header
`-=-=- StarDock Shipyard - Ship Registration -=-=-`, reached historically via a lowercase `s` at a
`Command [TL=...]` prompt) that this session's live server does **not** reproduce — `s`/`S` on
`scout_academy`'s server answers "Long Range Scan" instead, and no equivalent listing screen was
found anywhere else. Whether that fixture is from a different TWGS build/version, a different
server configuration, or a StarDock feature this specific game instance has disabled was not
determined this session.

`canon/strategy/ship-progression.md` already scopes the purchase send as a deliberately-deferred
"human-approved one-shot" — this capture attempt does not change that design, it just confirms the
**mechanism** (what to actually send once armed) has no ground truth on this server yet.

## What this means for WO-BUILD-STARDOCK-SHIP-PURCHASE-DRIVER

Per this repo's ground-truth-only screen-handling discipline (`trade_driver.py`, `state_parser.py`,
and `stardock_hold_driver.py`'s own "expects quote already on screen" contract, built only after
`tests/fixtures/stardock_cargo_hold_quote.txt` existed as a real captured shape) — writing a
purchase-confirm send against a guessed prompt would be exactly the fabrication this codebase's own
test suite exists to catch (see the `stardock_hold_driver.py` precedent: it parses a real captured
quote block, never invents one).

**Recommendation:** hold the send/confirm half of the driver until either (a) a live server that
does expose the `s`/shipyard-listing path is found and driven through an actual purchase to
capture the real confirm/deduction screen, or (b) a human manually captures it once on any TWGS
instance and drops the transcript into `tests/fixtures/`. The decision-engine side
(`ship_upgrade_decision.py`) and the listing parser (`introspector.parse_shipyard_listing`) are
already ground-truthed and need no further work — only the final "select + confirm + credits
leave" keystroke sequence is the open gap.

No code changes in this pass; this document is the deliverable, alongside a narrower follow-up
work order seed for the capture step specifically.
