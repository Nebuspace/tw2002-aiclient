# WO-BUILD-PROFIT-TARGET-HALT

**Status:** DONE · origin (see coord STATUS for SHA)
**Posted:** 2026-08-08 · orchestrator HANDOFF

## Goal

A fail-closed "stop once profit reaches target (e.g. 2x baseline)" STOP condition, mirroring
the existing X5 stop-loss floor's exact fail-closed shape (`_check_floor` /
`HALT_FLOOR_REACHED` / `HALT_CREDITS_UNKNOWN` / `HALT_CREDITS_STALE` /
`HALT_CREDITS_UNREADABLE`) with the comparison direction inverted. An ADDITIONAL stop
condition only -- not a new autonomy grant, not a new arming path.

## Scope

- `tw2002_aiclient/loops/player.py` -- `_check_profit_target`, four new `HALT_PROFIT_*`
  codes, `profit_target`/`profit_stale_ms` params on `replay_loop`, `_Observation.profit` /
  `_observe(want_profit=...)`, `ReplaySession.profit()` Protocol declaration.
- `tw2002_aiclient/session/autoloop.py` -- `_can_observe_profit`, `.profit()` adapter
  (`_ReplayPort`), `RunReport.profit_target`, `AutoLoopRunner.start(profit_target=...)`
  arm-time refusal (`profit_target_unsupported` / `invalid_profit_target`), wire report.
- `tw2002_aiclient/session/trade_chain.py` -- `TradeCaps.profit_target`,
  `TradeRunReport.profit_target`, `TradeChainRunner.start(profit_target=...)`,
  `ARGS_TRADE_CHAIN_START`.
- `tw2002_aiclient/trade_driver.py` -- per-hop profit-target check in `run_chain()`, using
  `_current_strict_credits` against the chain's `start_credits` (mirrors the existing
  `cash_floor` checks in the same module).
- `tw2002_aiclient/session/protocol.py` -- `autoloop_start` / `trade_chain_start` dispatch
  accept and validate `profit_target`.
- `tw2002_aiclient/cockpit/stopbanner.py` + `canon/architecture/control-and-escalation.md` --
  human labels + canon catalog rows for the four new codes.

## Constraints

- Fail-closed: unreadable / never-observed / stale profit reading halts, never proceeds as
  though under target.
- `profit_target=None` (the default) is a genuine no-op -- `.profit()` is never called,
  identical to the floor's `floor=None` contract.
- A target handed to a port that cannot observe profit is refused **at entry**, before any
  observation (mirrors the floor's `floor_unsupported` refusal) -- never a decorative flag.
- Re-checked at every replay boundary, not only at launch (mirrors the floor's
  per-boundary re-check).
- No new arming/autonomy path -- this only adds a stop condition to the existing autoloop /
  trade-chain send-time gate.

## Accept

- `_check_profit_target` ladder proven branch-by-branch (untargeted no-op, unobserved,
  wrong-type/truthy-tuple, freshness boundary, at-or-above-target boundary).
- `replay_loop` integration: positive control completes under target; boundary-0 halt;
  re-checked before every send (not only at launch); final boundary checked.
- Entry refusal: unenforceable port, non-int target, non-positive staleness window.
- AutoLoop wire: `profit_target` accepted + reported; `profit_target_unsupported` /
  `invalid_profit_target` refusals; a live-shaped run halts `profit_target_reached` when
  crossed.
- `TradeCaps.profit_target` defaults to `None`; `ARGS_TRADE_CHAIN_START` carries the arg.
- Closed-vocabulary + canon-label pins updated and green (`HALT_REASONS`,
  `stopbanner.INTERVENTION_REASON_LABELS`, `control-and-escalation.md`'s catalog table).

## Proof

STATUS + SHA · full targeted suite green (`tests/test_profit_target.py` new, plus
`test_credits_floor.py` / `test_turn_budget.py` / `test_loop_player.py` /
`test_autoloop_cycles.py` / `test_trade_driver.py` / `test_reflex_armed_run.py` /
`test_cockpit_stopbanner.py` regression-clean) · full suite run clean modulo two
pre-existing collection errors unrelated to this change (`test_analyze.py` /
`test_crawl_start_protocol.py`, missing `twclient` module on clean main).

## Refs

Orchestrator HANDOFF 2026-08-08 (two-step WO: this step, then
WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE gated on this step's STATUS). Mirrors
WO-P2-G4-X5-STOP-LOSS-FLOOR's shape exactly, per the HANDOFF's own instruction.
