# WO-EXPLORE-DECISION-TURNS — DECISIONS overlay shows turns remaining

**Status:** DONE · origin `70cffa6` (#248) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T08:17Z · hub (post-#247)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `9763fb0` (`explore_decision_lines_from_run` + dock/tolls flags)  
**Refs:** `#245`/`#246` DECISIONS overlay · `explore_status.run.turns_remaining`

## Goal

While explore is live, DECISIONS already shows intent, next hop, and dock/tolls.
Also disclose **turns remaining** from the wire when present — same pane, no
second surface — so the operator can see the budget the runner is actually
burning.

## Scope

- Extend `explore_decision_lines_from_run` to append a short turns line when
  `turns_remaining` is a non-bool int ≥ 0 (e.g. `turns 42`). Omit when absent
  or wrong type — never invent.
- Reuse existing overlay/poll/clear path (#245). No new poll.
- Focused pins + suite green. Live `n/a`.

## Constraints

- Display-only. No change to turn_budget rails / explore halt.
- #218 frozen. No §A.2 / new deps. Lead-seat only.

## Accept

1. Overlay includes turns when wire carries `turns_remaining`.
2. Absent/invalid → no turns line.
3. Suite green · live `n/a`.

## Proof

```bash
pytest -q tests/test_explore_decision_lines_wire.py
pytest -q tests
```
