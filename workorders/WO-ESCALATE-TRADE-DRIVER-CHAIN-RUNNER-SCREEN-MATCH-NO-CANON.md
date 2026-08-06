# WO-ESCALATE-TRADE-DRIVER-CHAIN-RUNNER-SCREEN-MATCH-NO-CANON

**Status:** DONE (Option C fact-find — clear; no re-escalate)
**Priority:** MED
**Gated:** no (Max carte blanche Option C)

## Goal

Report whether `trade_driver.run_chain()` re-validates per-hop `screen_match`
(or equivalent stop-on-unknown screen identity) every hop.

## Finding (tip `810538c`)

| Question | Answer |
|---|---|
| Kernel `screen_match` field checked in `run_chain`? | **No** — zero hits for `screen_match` in `trade_driver.py` |
| Per-step live screen re-validation? | **Yes** — `_navigate` (every warp along the hop path) calls `ctx.fresh()` + `classify_screen`; HOLDs unless class is movement/`main_command`; handles `warp_confirm` / avoid-DANGER. `_visit_port` HOLDs on unexpected commodity-cascade screens. |
| Ambiguous? | **No** — clear: classify-based STOP gates exist; rule-engine `screen_match` does not. |

Citations: `trade_driver.py` `_navigate` ~743–807 · `_visit_port` ~716–734 · `run_chain` hop loop ~934–958 · arming via `session/trade_chain.py`.

## Canon follow-through

Updated `canon/strategy/toll-and-defense.md` Code divergence bullet to record this
fact-find (no longer reads as "maybe missing re-validation").

## Accept

1. WO records the table above.
2. toll-and-defense divergence updated.
3. live-prove: n/a (read-only fact-find + docs).
