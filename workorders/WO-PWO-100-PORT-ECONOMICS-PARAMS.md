# WO-PWO-100-PORT-ECONOMICS-PARAMS — hypothesis-tagged port-economics substrate

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T04:03:29Z  
> Type: product substrate · PWO-100  
> Tip base: `73e7428`

## Goal
Ship a standalone **hypothesis-tagged** port-economics params module so product stats are not silent hardcoded literals in `trade_adapter`.

## Scope
- A: `tw2002_aiclient/port_economics.py` (new)
- B: wire `trade_adapter` floors/ceiling/spread re-exports from A
- C: `tests/test_port_economics.py` (tag presence + adapter source guard + coach port keys)
- D: ULTRACODE + P8 PREP tip honesty → LIVE for 100 residual
- E: this WO file

## Constraints
- Do **not** invent Layer-B / introspected game_data under 100's cover
- PWO-114 CI enforcement stays out of scope
- No live TWGS / money-path arm
- No send paths

## Accept
1. Floors / ceiling / spread authored only as `HypothesisParam` (`tag=hypothesis`, `verified_vs_live=False`)
2. `trade_adapter` has no silent `"Fuel Ore": 20.0` literal; re-exports from `port_economics`
3. Coach port-economics keys loadable with required `verified_vs_live` field
4. Unit + tag-presence tests green

## Proof
`pytest tests/test_port_economics.py` · CI suite · live-prove n/a (offline params substrate)
