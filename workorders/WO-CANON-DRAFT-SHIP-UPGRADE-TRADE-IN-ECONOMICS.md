# WO-CANON-DRAFT-SHIP-UPGRADE-TRADE-IN-ECONOMICS

**Status:** IN FLIGHT (impl-aiclient-h1 · hub GO 2026-08-12T04:18:34Z)

## Goal

Close the ship-upgrade payback honesty gap: tip amortized **gross list price** and ignored
shipyard **trade-in** credit, so ROI is systematically pessimistic on worlds that credit the
outgoing hull.

## Scope

- `canon/strategy/ship-progression.md` — document net cash-outlay payback + omit-until-known rule
- `canon/DECISIONS.md` — `DECISION-SHIP-UPGRADE-TRADE-IN-ECONOMICS` (hub GO this ticket)
- `tw2002_aiclient/ship_upgrade_decision.py` — optional `trade_in_credit` (default `0` = unknown /
  pessimistic; never invent a %)
- `tests/test_ship_upgrade_decision.py` — trade-in shortens payback; default path unchanged
- This WO file

## Out of scope

- Live shipyard purchase / trade-in capture driver (still NOT-ATTEMPTED on research axes)
- Inventing a server-wide trade-in percentage
- Auto-spend / purchase adapter (still HELD per PWO-107)
- `WO-CLEANUP-PORT-ECONOMICS-UNUSED-STRATEGIES-PATH` (overlaps cursor CURRENT)

## Research (verify-first)

| Finding | Evidence |
|---|---|
| Payback uses `ship.cost + hold_fill` with no trade-in term | tip `ship_upgrade_decision.py` `payback_turns` (`total_cost = ship.cost + hold_fill_cost(...)`) |
| Backlog premise | `backlog-aiclient.md` MED row: "payback model has no trade-in term → systematically pessimistic if servers grant trade-in" |
| Live trade-in formula **not** ground-truthed here | `canon/research/stardock-ship-purchase-capture-2026-08-08.md` / fighters-cargo-ship coverage: shipyard confirm + credit delta NOT-ATTEMPTED / no spend |
| Classic TWGS often credits outgoing hull toward a new ship | Named as research axis in `WO-LIVE-DRIVE-AUTOPILOT-RESEARCH.md` item 5; not a tip-measured constant |

## Accept

1. Canon states: amortize **net cash outlay** = `max(0, candidate.list_price − trade_in_credit) + hold_fill`; unknown trade-in → treat as `0` (safe pessimistic HOLD bias); never invent %.
2. Pure engine accepts `trade_in_credit: int = 0` and uses it in payback; existing callers unchanged.
3. Unit test: known trade-in yields strictly shorter payback than gross-only for the same candidate.
4. DECISION logged citing hub GO.

## Proof

- `.venv/bin/python -m pytest tests/test_ship_upgrade_decision.py -n0 -q`
- Offline docs/code only → `live-prove: n/a` (no login/session/play path)

## Refs

- Hub ACK 2026-08-12T04:18:34Z (GO on this WO)
- `canon/strategy/ship-progression.md` § ROI-vs-turn-budget
- `DECISION-PWO-107-SHIP-UPGRADE-DECISION-PORT`
