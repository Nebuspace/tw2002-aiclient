# WO-FIX-FIGHTER-TOLL-HUMAN-APPROVAL-GATE

**Status:** IMPLEMENTING
**Posted:** 2026-08-08 · IDLE-KICK MED continuation after #570 · carte-blanche ruled READY (sw2102-docs DECISIONS.md fighter-toll-human-approval-gate)

## Goal

Add the per-behavior (approve-once) human-approval gate canon already requires for
auto-selected NPC Attack tolls. `decide_encounter` already has never-auto-Pay /
retreat-on-unparsed / NPC-scoped / force_share guards — missing only this spine gate.
Closing a documented gap, not granting new autonomy.

## Scope

- `tw2002_aiclient/session/fighter_toll_policy.py` — `attack_approved` gate on
  `decide_encounter` / `next_encounter_input` (fail closed default).
- Call sites that intentionally fire the built-in (`login.py`, `sector_explore.py`)
  pass `FIGHTER_TOLL_ATTACK_BEHAVIOR_APPROVED` explicitly.
- `tests/test_fighter_toll_policy.py` (+ any decide_encounter callers that expect `A`)
  — pin: winnable + unapproved ⇒ Retreat; winnable + approved ⇒ Attack.
- `tw2002_aiclient/action_safety.py` — coverage row for the new gate.
- Canon divergence tense closes in `alignment-and-conduct.md` / `toll-and-defense.md`
  (docs win — mark tip-closed).

## Constraints

- Fail closed: `attack_approved=False` (default) never selects `A`, even when
  force_share / band gates pass — Retreat with a stable reason.
- Do not change never-auto-Pay, PvP hard-stop, or reserve-floor quantity clamp.
- Approve-once (behavior), not per-fire human confirm at every toll.
- live-prove **n/a** (offline policy).

## Accept

1. Unapproved winnable NPC toll ⇒ `key=="R"` and reason names the approval gate.
2. Approved winnable NPC toll ⇒ `key=="A"` (existing force_share pins stay green).
3. Production explore/login paths pass the named built-in approval constant.
4. Coverage map lists the gate with a proof marker.

## Proof

Targeted pytest on `tests/test_fighter_toll_policy.py` (+ reroute decide_encounter pin).
