# WO-PLAYER-HALT-NEVER-AUTO-CLASS — Qualify LoopPlayer never-auto halt with class

**Status:** OPEN · EXECUTE · MED · diagnosis honesty (follow-on #213)
**Posted:** 2026-07-29T05:40Z · morning bar complete; hygiene/honesty continuity
**Seat:** impl-claudecode-aiclient (offline) · live → n/a (vocabulary; no new live path)
**Depends:** #213 explore halt vocabulary on main (`a8f2bc8`)
**Refs:** `loops/player.py` `_gate` · `HALT_REASONS` / `LoopResult` validation · explore `_qualify` in `session/sector_explore.py` · CC bank note 2026-07-29T05:39Z

## Why

Explore now reports `never_auto_action:<klass>`. LoopPlayer still returns bare `never_auto_action`. Honest *today* while `NEVER_AUTO_ACTION_CLASSES` has one member (`money_prompt`), but ambiguous the moment the set grows — the latent twin of the #213 defect. Carry the class now, before that growth.

## Goal

When `_gate` refuses a never-auto class, the halt reason is `never_auto_action:<klass>` (same shape as explore). `unknown` stays bare `unrecognized_screen`. Halt *behavior* unchanged.

## Accept

1. `_gate` on a never-auto class → `never_auto_action:<klass>` (literal, class from observation — not a hardcoded class string).
2. `LoopResult` / `HALT_REASONS` validation accepts the qualified form (prefix before `:` is a known halt code). Do not explode the frozenset into every class×reason pair.
3. STOP banner still renders a human label for the qualified form (lookup by base code before `:`; class may appear in raw text — do not invent new catalog rows per class).
4. Pins: money_prompt → exact `never_auto_action:money_prompt`; a second never-auto class (fixture / temporary set member in test) proves the class is taken from observation, not a constant; collapse-to-bare mutation goes red.
5. `unknown` path unchanged (`unrecognized_screen`). No invent of `halt_not_drivable` on the player loop (player only auto-drives taught macros; not-drivable is explore-specific).
6. Suite · STATUS · Live: **n/a** (vocabulary-only; money_prompt refuse already proven).

## Constraints

- Do not claim `Your offer` as `money_prompt`.
- Do not implement option-2.
- Do not grow / split `app.py`.
- Prefer shared `_qualify` helper only if it lands in a neutral module without pulling explore into player (duplicate 3-line helper OK; do not create a premature shared package).
- Public-safe only.

## Proof

```text
pytest tests/test_never_auto_action.py tests/test_autoloop.py tests/test_credits_floor.py tests/test_cockpit_stopbanner.py -q -n0
# + suite on PR
# Mutation Proof: name each mutation and the specific test that must redden
#   e.g. hardcode money_prompt in qualify → second-class pin red
#   strip qualify / return bare never_auto_action → money_prompt exact pin red
```

## Out of scope

- `app.py` line-cap split
- Option-2 decline path
- Expanding `NEVER_AUTO_ACTION_CLASSES` membership (only the reason string for members that already exist)
