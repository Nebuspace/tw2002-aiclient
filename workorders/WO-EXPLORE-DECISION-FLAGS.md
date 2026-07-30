# WO-EXPLORE-DECISION-FLAGS — DECISIONS lines disclose dock/tolls arm state

**Status:** DONE · origin `707efa6` (#246) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T07:57Z · hub (post-#245)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `912361e` (`run.next_sector` + `run.dock_new_ports` on wire)  
**Refs:** `#245` DECISIONS overlay · `#212`/`#227` Gather/dock chrome · `explore_decision_lines_from_run`

## Goal

Live explore DECISIONS already shows intent + next hop. The same overlay should
honestly disclose whether the run was armed with **dock** / **fight_tolls** —
facts already on `explore_status.run` — so the pane matches the confirm line
the operator said `y` to.

## Scope

- Extend `explore_decision_lines_from_run` (or a thin sibling used only by that
  path) to append a short flags line when `dock_new_ports` / `fight_tolls` are
  present on the run dict (e.g. `+dock` / `+tolls` / both / neither — match
  existing explore-offer vocabulary from `explore_flags` if cheap).
- Do **not** invent flags when keys absent; prefer explicit `false` on wire.
- Play overlay continues to clear on stand-down (no new poll path).
- Focused pins for composer shapes; suite green.

## Constraints

- Display-only — no change to explore defaults, halt, or arm gates.
- Reuse vocabulary; no second string table if `explore_flags` already has
  markers.
- #218 frozen; no §A.2 / new deps / tooling. Lead-seat only.
- Live prove: `n/a`.

## Accept

1. DECISIONS explore overlay discloses dock/tolls consistent with `run.*`.
2. Absent/false stays honest (no invented +dock).
3. Suite green · live `n/a`.

## Proof

```bash
pytest -q tests/test_explore_decision_lines_wire.py  # + flag pins
pytest -q tests
```
