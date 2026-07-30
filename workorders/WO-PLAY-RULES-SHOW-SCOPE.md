# WO-PLAY-RULES-SHOW-SCOPE — U)rules lists typed `scope`

**Status:** DONE · origin `5b1afb5` (#240) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T04:45Z · hub (after #239 scope identity)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `d3d82fe` (Play collects `scope`)  
**Refs:** `cockpit/rules_library.py` · `#238` U)rules · `#239` scope field

## Goal

`#239` writes typed `scope` onto blessed rules, but `U)rules` (#238) still
shows only `rule_id` / `do` / `screen_match` / `priority`. The operator who
just typed `repeating` cannot see it in the library peek.

Add `scope` to the blessed-row projection and row formatting so the peek
matches what Analyze identity collected.

## Scope

- Extend `blessed_rows` / `_format_row` (or equivalent) to include `scope`.
- Focused pin: a blessed `repeating` rule shows `repeating` (or clear
  `scope=repeating`) in the composed peek lines; `one-shot` likewise.
- Unknown/missing scope → honest `?` (never invent `one-shot` in the peek).

## Constraints

- Read-only; no arm/send/identity/V change.
- No cycle run-loop work.
- `#218` frozen — touch `rules_library` (+ tests); avoid `app.py` unless
  unavoidable.
- Live prove: `n/a`.

## Accept

1. `U)rules` rows include the rule's typed `scope`.
2. Missing/unknown scope displays as `?`, not a minted `one-shot`.
3. Focused tests + suite green.
4. Live prove: `n/a`.

## Proof

```bash
pytest -q tests/test_play_rules_library.py
pytest -q tests
```
