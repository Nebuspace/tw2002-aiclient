# WO-FIX-CLASSIFIER-PORT-TRADE-EMIT

**Status:** DONE (false premise — tip already emits; doc tip-close)
**Priority:** LOW
**Gated:** no

## Goal

Cycle-42 claimed `classify_screen` never emits `port_trade` (only `cim_report`).
Verify-first: tip already emits `port_trade` via content anchors; tests green.

## Resolution

- **Code:** no change — `session/classify.py` `_CONTENT_ANCHORS` includes `port_trade`;
  `tests/test_classify.py::test_port_trade` passes.
- **Doc:** correct stale "not emitted … fixture corpus" note in
  `canon/engine/coaching-engine.md` § Code divergence / docked_at_port paths.

## Accept

1. coaching-engine no longer claims `port_trade` is unemitted.
2. `test_port_trade` stays green.
3. live-prove: n/a (docs tip-close + offline classifier already covered).
