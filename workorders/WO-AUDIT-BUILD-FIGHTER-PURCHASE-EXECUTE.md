# WO-AUDIT-BUILD-FIGHTER-PURCHASE-EXECUTE

**Status:** DONE for tip-honesty slice (pending merge) · **EXECUTE BANKED** (Max GO + live Class-0 price)
**Priority:** LOW
**Seat:** `impl-aiclient-cursor`
**Depends-on:** live/captured Class-0 fighter unit price before any tip constant or buy driver
**Gated:** **yes** for buy EXECUTE / money-path arm · **no** for this docs honesty pass

## Goal (this PR)

Stop priority-engine from implying tip ships `afford_fighters()` / a measured
`FIGHTER_UNIT_PRICE_CLASS0`. Record tip reality (GOALS paint only) and keep buy EXECUTE Planned.

## Out of scope (this PR)

- Implementing `FighterAffordability` / tip `FIGHTER_UNIT_PRICE_CLASS0`
- One-shot buy EXECUTE mirroring `stardock_hold_driver`
- Live TWGS arm / diversity prove for a purchase

## Accept (honesty)

1. Rows #6/#7 Status cells no longer claim tip `afford_fighters()`.
2. Fighter economics section states tip gap + Max-gated EXECUTE follow-on.
3. Code-divergences list names the canon-ahead fighter affordability gap.
4. live-prove: `n/a` (docs-only).

## Future Accept (Max GO — separate WO / reopen)

1. Class-0 unit price from live/captured fixture (not community hypothesis alone).
2. Guarded one-shot buy EXECUTE mirroring `stardock_hold_driver` arm/STOP shape.
3. Offline suite + live-prove diversity (or explicit Max sacrificial GO).

## Proof

`git grep afford_fighters\|FIGHTER_UNIT_PRICE_CLASS0 -- '*.py'` → empty on tip;
canon rows cite GOALS / Planned EXECUTE.

## Refs

- queue-aiclient.md `AUDIT-BUILD-FIGHTER-PURCHASE-EXECUTE`
- `canon/engine/priority-engine.md` · AP-09 in archive-port-patterns
- `cockpit/goals.py` (`fighters_aboard`, `fighter_buy_status`)
