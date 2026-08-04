# WO-AUDIT-CANON-DRAFT-CHAIN-THRESHOLD-RATIONALE

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** LOW
**Depends-on:** none
**Gated:** no — docs honesty; ≥4 rationale already in canon prose (not a Max number ruling)

## Goal

Make priority-engine row #13's "hull deferred until ≥4" cite the existing execute-floor
rationale (and tip `chains.py` home) so the number does not read as unexplained magic.

## Scope

- `canon/engine/priority-engine.md` row #13 Status cell → anchor + trade-loops §
- `canon/strategy/trade-loops.md` — replace stale `priority_engine.py` cites with tip `chains.py`
- This WO file

## Accept

1. Row #13 links to Chain execute-floor thresholds / `MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE=4` rationale.
2. trade-loops tip-home for the three constants is `chains.py` (not archived priority_engine).
3. live-prove: `n/a` (docs-only). No new Pending Max ruling — design prose already existed.

## Proof

`rg 'MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE|#chain-execute-floor' canon/engine/priority-engine.md`
+ STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-CHAIN-THRESHOLD-RATIONALE`
- `tw2002_aiclient/chains.py` (`MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE = 4`)
- DECISIONS.md Pending — chain floors (constants live in `chains.py`)
