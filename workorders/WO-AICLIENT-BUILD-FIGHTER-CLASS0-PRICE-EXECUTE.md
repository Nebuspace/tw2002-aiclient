# WO-AICLIENT-BUILD-FIGHTER-CLASS0-PRICE-EXECUTE

**Priority:** MED  
**Claimed-by:** impl-aiclient-h1

## Goal

Status producer for Class-0 fighter unit price → wire into
`afford_fighters` / GOALS via `fighter_unit_price` /
`fighter_price_class0`. **No** purchase EXECUTE (Max-gated). **No**
invented measured `FIGHTER_UNIT_PRICE_CLASS0` tip constant.

## Changes

- `tw2002_aiclient/fighter_price_status.py` — `FighterPriceScalars`
  observe/parse/merge; provisional fail-closed parsers
- Wire `PlayShellScreen.fighter_price_scalars` + status wrap in `app.py`
- Canon `priority-engine.md` tip-honesty + divergence #6 updated
- Tests: parse fail-closed, observe/merge, GOALS path, no tip constant

## Out of scope

- Live menu discovery to *call* `observe` on a real TWGS screen
  (`WO-BUILD-FIGHTER-CLASS0-LIVE-PRICE-CAPTURE` still open — research
  2026-08-09: StarDock reached, price line not found)
- Buy EXECUTE / money-path arm

## Accept

- [x] Status keys written only after observe / successful parse
- [x] No tip `FIGHTER_UNIT_PRICE_CLASS0`; no EXECUTE path
- [x] `afford_fighters` / GOALS consume merged keys
- live-prove: **n/a** (offline producer + recommend wire; no send path;
  live capture remains a separate open WO)

## Proof

```bash
.venv/bin/python -m pytest tests/test_fighter_price_status.py tests/test_fighter_affordability.py -q -n0
rg -n 'FIGHTER_UNIT_PRICE_CLASS0' tw2002_aiclient/   # expect 0 product constants
```
