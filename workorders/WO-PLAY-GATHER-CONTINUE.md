# WO-PLAY-GATHER-CONTINUE — Gather port data without halting Explore

**Status:** APPROVED · orchestrator-owned lead-seat build  
**Approved:** 2026-07-30 · Max selected guarded-chain contract  
**Branch:** `wo/PLAY-GATHER-CONTINUE`

## Goal

Keep Gather and Trade separate: Gather docks first-sight ports, records the
commerce table, declines every recognized commodity quantity with `0`, and
returns Explore to the ordinary command prompt without buying or selling.

## Scope

- `tw2002_aiclient/session/sector_explore.py`
- `tw2002_aiclient/session/cli.py`
- `tests/test_explore_dock_new_port.py`

## Constraints

- No Attack path; dock-letter allowlist remains exactly `P`/`T`.
- `0` may be sent only on an exact captured commodity quantity prompt after
  this armed Gather run has ingested a genuine commerce report.
- Fresh render/classification before every decline.
- At most three declines (the fixed commodity vocabulary); any offer,
  unexpected prompt, settle failure, or fourth quantity halts.
- No offer acceptance, transaction, credit change, opportunistic trade, or
  discovered-chain execution in this slice.
- CLI and daemon library defaults remain OFF; Play Gather default remains ON.

## Accept

1. A tradeable port no longer ends Explore at
   `never_auto_action:money_prompt`.
2. The exact send sequence is `P`, `T`, then bounded `0` declines; no Enter
   overshoot accepts a default quantity or offer.
3. The port commodities are still persisted before the decline cascade.
4. After the final decline, control is back at `main_command` and Explore may
   issue its next warp.
5. Non-quantity money prompts and unknown screens still halt with zero blind
   sends.

## Proof

- Focused dock/gather tests, including one/two/three commodity cascades,
  unexpected offer, fourth-prompt bound, and next-warp sequencing.
- Full offline suite.
- Live safe-half prove: Gather on a tradeable port, verify zero quantity,
  unchanged credits/cargo, continued Explore. No armed chain trade in this WO.
