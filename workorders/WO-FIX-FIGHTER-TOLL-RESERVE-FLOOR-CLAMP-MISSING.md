# WO-FIX-FIGHTER-TOLL-RESERVE-FLOOR-CLAMP-MISSING

**Status:** IMPLEMENTING · PR #568
**Posted:** 2026-08-08 · orchestrator HANDOFF HIGH batch (carte-blanche ruled READY)

## Goal

Add the reserve-floor clamp on Attack-toll quantity auto-commit so
`decide_quantity()` cannot spend the ship's entire fighter complement.
Bug fix to an already-documented guarantee (`toll-and-defense.md` ·
`action-safety-guards.md`), not a new autonomy grant.

## Scope

- `tw2002_aiclient/session/fighter_toll_policy.py` — `decide_quantity` (and
  `next_encounter_input` pass-through) honor `reserve` / `DEFAULT_FIGHTER_RESERVE`.
- `tests/test_fighter_toll_policy.py` — pins: spendable = max_avail - reserve;
  cannot commit full complement; halt when needed qty would breach reserve.

## Constraints

- Fail closed: if matching `theirs` would leave aboard &lt; reserve, STOP (no key),
  do not under-commit into a losing fight and do not breach the floor.
- Do not invent Pay / PvP / human-approval changes (separate MED WO).
- `decide_encounter`'s unused `reserve` param stays call-site compatible; this WO
  load-bears on the quantity path canon names.

## Accept

1. `decide_quantity(..., reserve=R)` never returns a commit &gt; max(0, max_avail - R).
2. When `theirs` &gt; spendable, halt with a stable reason (no keystroke).
3. Existing qty pins (unreadable → STOP, band exceeded, enemy-count commit) stay green.
4. live-prove **n/a** (offline policy).

## Proof

Targeted pytest on `tests/test_fighter_toll_policy.py`.
