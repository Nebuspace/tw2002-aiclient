# WO-BUILD-STARDOCK-SHIP-PURCHASE-DRIVER

**Status:** BLOCKED — capture gap found, see finding doc
**Posted:** 2026-08-08 · orchestrator carte-blanche batch HANDOFF

## Goal

New execution driver: act on the existing ship-purchase decision engine
(`ship_upgrade_decision.py`, PWO-107) to actually buy a ship at StarDock when it scores
favorably. Must mirror `trade_driver.run_chain`'s `is_armed`/`should_abort`/fail-closed-floor
shape exactly. Sacrificial-account scope only.

## Scope

- New sibling module(s) modeled on `stardock_hold_plan.py` / `stardock_hold_driver.py` /
  `session/stardock_hold.py` (identity+plan, one-pass driver, daemon runner) — a
  `StardockPurchasePlan` + `run_ship_purchase()` + `StardockPurchaseRunner`.
- Consumes `ship_upgrade_decision.UpgradeDecision` / `choose_upgrade()`.
- Listing/catalog parse already ground-truthed (`introspector.parse_shipyard_listing`,
  `tests/fixtures/stardock_shipyard_listing.txt`) — no further work needed there.

## Constraints

- Ground-truth-only screen handling (this repo's standing discipline — `trade_driver.py`,
  `state_parser.py`, and `stardock_hold_driver.py`'s own "expects quote already on screen"
  contract) — never invent a prompt/confirm shape without a real captured transcript.
- Sacrificial-account scope only (`crawl_sacrificial=True`).
- Human-approved one-shot per `canon/strategy/ship-progression.md` — the actual credit spend
  stays an approve/reject moment, never a bare autonomous send.

## Blocker

Live-drive capture pass on `scout_academy` (2026-08-08) reached StarDock (sector 8039, found via
`V` View Game Status), fully explored the docking commerce menu, the Corp Menu, and the Onboard
Computer's Ship Catalog (`C`→`C`, read-only specs browser) — **no purchase-confirm prompt was
reachable anywhere in this session's live menu tree.** The repo's own
`tests/fixtures/stardock_shipyard_listing.txt` fixture (reached historically via a lowercase `s`)
does not reproduce on this server (`s`/`S` answers Long Range Scan instead). Full writeup:
[`canon/research/stardock-ship-purchase-capture-2026-08-08.md`](../canon/research/stardock-ship-purchase-capture-2026-08-08.md).

No credits were spent during the capture attempt (balance unchanged: 97,809).

## Accept

Deferred pending either (a) a live server that does expose the shipyard-listing path, driven
through an actual purchase to capture the real confirm/deduction transcript, or (b) a manual
human capture on any TWGS instance dropped into `tests/fixtures/`. Decision-engine and listing
parser sides need no further work.

## Proof

Research finding doc committed; no code changes this pass (writing send logic without ground
truth would be fabrication, per this repo's standing discipline).

## Refs

Orchestrator carte-blanche batch HANDOFF 2026-08-08 ("highest priority... directly serves the
original directive"). `canon/strategy/ship-progression.md` (purchase-is-human-approved design).
`stardock_hold_driver.py`/`stardock_hold_plan.py` (the precedent this driver was to mirror).
