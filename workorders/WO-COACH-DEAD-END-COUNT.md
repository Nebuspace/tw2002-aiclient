# WO-COACH-DEAD-END-COUNT

**Status:** DONE · origin `df862ad` (#260) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Depends:** `main` ≥ `fc39277` (#259)

## Goal

Wire coaching's `dead_end_count` from an honest off-draw world-model scan so the
authored dead-end / hide-planet card (`at_dead_end`) can fire. Teaching only.

## Canon

`canon/engine/coaching-engine.md`: `genesis_count` / `dead_end_count` have no
status producer; trigger map emits `at_dead_end` when either count > 0.
Colonization siting cares about **sector** dead-ends (one warp), not menu-map
signature dead-ends (`menu/map_view.py`).

## Scope

- Extend `WorldStats` (or tiny sibling) on the existing refresh cadence.
  Count sectors with `warps` length == 1 from world-model (lazy import inside
  refresh only).
- Merge `dead_end_count` onto Play status when observed; document omit-vs-zero
  honesty (prefer: completed scan may report 0; pre-scan omits).
- `cockpit/decisions.py`: pass `dead_end_count=` when status carries a real
  non-negative int; fail-closed on hostile shapes.
- Optional same-pass `genesis_count` **only** if an existing honest reader
  already exists without inventing a catalog_provider — otherwise leave for a
  follow-on and state that in STATUS.
- Focused pins + offline suite.

## Constraints

- No draw-path `world_model` import.
- Do not reuse menu-map dead-ends as sector dead-ends.
- No prompt / send / arm / run/ touch.
- Lead-seat direct (no Task/subagents this session).
- live-prove `n/a`.

## Accept

1. World with ≥1 one-warp sector → `dead_end_count` ≥ 1 on status after refresh;
   idle DECISIONS can show the authored dead-end card.
2. Pre-scan omit (or completed-empty 0 — pick one, pin it).
3. Hostile status/world never raises; never invents a positive count.
4. Draw-path cold pin holds.
5. Focused + full offline suite green.
6. live-prove `n/a`.

## Proof

```bash
pytest -q tests/test_world_stats.py tests/test_cockpit_decisions.py
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- `canon/engine/coaching-engine.md` I2 + Code divergence
- `canon/strategy/planet-colonization.md` / dead-end card in `strategies.json`
- Plan: Nebuspace `.samantha/plans/coach-dead-end-count-2026-07-30.md`
