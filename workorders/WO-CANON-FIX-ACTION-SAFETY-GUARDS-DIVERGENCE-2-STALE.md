# WO-CANON-FIX-ACTION-SAFETY-GUARDS-DIVERGENCE-2-STALE

**Status:** READY · gated: no (docs-only)
**Posted:** 2026-08-08 · orchestrator HANDOFF

## Goal

`canon/doctrine/action-safety-guards.md`'s "Code Divergence #2" section (lines ~261-270) describes
`EXPLORE_BASELINE_EV` as if it currently drives autonomous action-selection in contradiction to the
stop-on-unknown/novelty-halt invariant. Verify-first re-check (2026-08-08) found this is stale: the
same document's own citation [6] (lines ~294-295) already correctly states `EXPLORE_BASELINE_EV` is a
"suggestion-only FOCUS floor" and that the actual never-idle EV-selector divergence #2 describes lived
in the archived `priority_engine.py`/`autopilot.py`, already retired and flagged do-not-revive.

Code-level confirmation: `EXPLORE_BASELINE_EV` (`tw2002_aiclient/focus_status.py:30`) has exactly one
consumer — `recommend_focus_candidates` sets a display-only `ev_per_turn` field (`:242`). A full-repo
grep for `EXPLORE_BASELINE_EV` outside `focus_status.py` returns zero hits. `FocusScalars` (the type it
feeds) is consumed only by `game_data_stats.py`, `ship_upgrade_decision.py`, and `screens.py` — a
render/display path, not the autonomous strategic run-loop's action-selection.

## Scope

`canon/doctrine/action-safety-guards.md` only — tense-correct the Divergence #2 prose (lines ~261-270)
to match citation [6]'s already-correct present-day framing: the never-idle EV-selector contradiction
was real in the archived `priority_engine.py`, is resolved by that module's retirement, and today's
`EXPLORE_BASELINE_EV` is confirmed suggestion-only with no autonomous-action consumer.

## Constraints

- Docs-only. No code changes — the code is already correct/safe, only the doc's tense/framing is stale.
- Do not remove the historical record of the divergence (it's still useful history) — just stop
  describing it in the present tense as if still live.
- Keep citation [6] and its Ref list intact; align the body prose to what it already says.

## Accept

Divergence #2's prose reads as a resolved historical finding (not a live contradiction), consistent
with citation [6]. No other content in the document changes.

## Proof

Diff limited to `canon/doctrine/action-safety-guards.md`. No test suite implication (docs-only).

## Refs

Orchestrator HANDOFF 2026-08-08 (carte-blanche batch, verify-first reverify); sw2102-docs-style ruling
recorded in `sw2102-docs/DECISIONS.md` "explore-baseline-ev-vs-novelty-halt" (2026-08-08 batch) —
same reasoning, this WO is the tw2002-aiclient-side canon-fix half of that closure.
`tw2002_aiclient/focus_status.py:30,242`; `action-safety-guards.md:261-270` vs `:294-295`.
