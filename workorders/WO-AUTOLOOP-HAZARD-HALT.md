# WO-AUTOLOOP-HAZARD-HALT — last structural rail before `cycles`

**Status:** DONE · origin `1d81492` (#242) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T05:48Z · hub (after #241 turn-budget → 3/4 rails)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `2a969e6` (turn-budget LIVE; docstring says hazard NOT)  
**Refs:** `session/autoloop.py` "One pass / STILL no cycles" · `canon/doctrine/action-safety-guards.md` § Hazard-halt · `#241`

## Goal

Land the **hazard-halt** rail on AutoLoop / `replay_loop` so the four
repeating rails are complete. After this WO, a *follow-on* may unlock
`cycles` / `scope: repeating` run-loop — **this WO still refuses `cycles`.**

Canon hazard-halt (fail closed → escalate):

- zero-fighter state
- unrecoverable game-select
- settle-desync marked never-safe-to-proceed

## Scope

- Wire hazard checks at the same player choke-point family as floor /
  turn-budget (before send / cycle boundary).
- Prefer existing observers (`observe_fighters` / fighters snapshot,
  classify `game_select`, settle never-safe flags) — do not invent a
  second sensing stack.
- Typed halt codes + STOP banner labels + catalog rows (match house
  pattern from turn-budget).
- Update autoloop docstring: **4 of 4 rails built**; `cycles` still
  refused in *this* WO (unlock is a separate follow-on once pins prove
  the set).
- Focused tests: each hazard shape halts with typed reason; unbudgeted /
  non-hazard runs unchanged; `cycles` still refused.

## Constraints

- **`cycles` / `force` / `param` remain REFUSED** here — do not unlock
  repetition in this PR.
- No Play `V` / reflex_arm behavior change beyond inheriting the new halt.
- `#218` frozen — prefer `autoloop.py` / `player.py` / `protocol.py` /
  stopbanner / catalog; smallest surface only.
- No §A.2 / new deps / tooling.
- Live prove: `n/a` (offline rail) unless hub asks a safe refusal half.

## Accept

1. Documented hazard shapes halt with typed codes before further sends.
2. Non-hazard armed runs behave as today (floor + turn-budget unchanged).
3. `cycles` still refused (pin).
4. Docstring tally: 4/4 rails built; cycles unlock deferred to follow-on.
5. Focused tests + suite green.
6. Live prove: `n/a`.

## Proof

```bash
pytest -q tests/test_turn_budget.py tests/test_autoloop.py  # + new hazard pins
pytest -q tests
```

STATUS names halt codes and confirms cycles still refused.

## Follow-on (not this WO)

- `WO-AUTOLOOP-CYCLES` / Play `scope: repeating` run-loop unlock.
- Max sacrificial GO: live `V`→`y` arm (#235 NOT-ATTEMPTED).
