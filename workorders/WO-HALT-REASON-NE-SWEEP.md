# WO-HALT-REASON-NE-SWEEP — Harden `!=` assertions against bare halt codes

**Status:** DONE · origin `91da221` (#215) · tip-honesty stamp 2026-07-31 (product on main; banner was stale OPEN)
**Seat:** impl-claudecode-aiclient · live n/a
**Depends:** #214 on main (`da94f0e`)
**Refs:** CC STATUS 2026-07-29T05:55:49Z · `halt_reason_code()` in `loops/player.py`

## Why

Qualifying halt reasons (`never_auto_action:<klass>`) turns every *positive* assert red (loud). Negative asserts `x != HALT_NEVER_AUTO_ACTION` stay green even when `x` is `never_auto_action:money_prompt` — they quietly stop excluding what they name, often in files the qualify change never touched. #214 fixed the four known sites; a wider sweep is still owed.

## Goal

Every test (and production guard) that means "not a never-auto halt" / "not unrecognized" must compare via `halt_reason_code(reason)` (or equivalent base-before-colon) when the value under test can be qualified — never bare-string `!=` against a code that now has a qualified form.

## Accept

1. Sweep `tests/` (and any product `!=` against halt reason constants that can be qualified) for bare `!=` / `==` pitfalls against `HALT_NEVER_AUTO_ACTION`, `HALT_UNRECOGNIZED_SCREEN`, and other codes that now accept `code:detail`.
2. Fix weakened negatives to use `halt_reason_code(...)` (player) or the explore equivalent if present; do not invent a second parser.
3. Pin: a deliberately wrong qualified never-auto reason must fail the strengthened negative (mutation or dedicated pin).
4. Suite green · Live **n/a** · no app.py growth · no option-2 · no Your-offer claim.
5. Mutation Proof: name each mutation + the test that must redden.

## Constraints

- Tests/instrument only preferred; product changes only if a real `!=` guard exists outside tests.
- Do not expand `NEVER_AUTO_ACTION_CLASSES`.
- Public-safe only.

## Proof

```text
rg '!= .*HALT_|!= .*(never_auto_action|unrecognized_screen)' tests/ tw2002_aiclient/
pytest -q -n0  # targeted then suite on PR
```
