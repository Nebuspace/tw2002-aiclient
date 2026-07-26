# WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT

**Status:** DONE · PR #38 · origin `29025dd`  
**Posted:** 2026-07-26 · from `audit/session-classify-audit-coverage-20260726.md` C-01  
**Base tip:** `origin/main` (`0809902` or newer)

## Goal

Close the honest hazard around bare `classify()` vs `classify_screen` — **not** by chasing unreachable whole-text “parity,” but by making the live-path contract load-bearing.

## What the audit got right / wrong (CC probe 21:16:27Z)

- **True:** `classify()` does not call `_is_plain_timed_out_game_select`; `classify_screen` does.
- **Not the bite:** On the plain Timed Out + Select-a-game shape where the helper is load-bearing, both APIs still returned `game_select` (whole-text anchor path). Adding the helper alone is consequentialness-light.
- **Actual unsafe divergence (stale scrollback):** stale `"Select a game :"` above a different live prompt → `classify_screen(text, prompt) -> menu` (correct) vs `classify(whole_text) -> game_select` (wrong). Same defect class as login whole-grid false `T`: match with nothing establishing the screen is current.

## Scope

- `tw2002_aiclient/session/classify.py` docstring / contract for `classify()`
- Pins + any small enforcement (lint/test) that live rendered-screen callers use `classify_screen`
- Optional: add the missing plain-timeout helper to `classify()` **only if** it helps a documented one-string use case — not as the primary Accept
- **Out:** Explore HOLD · invent classes · live proves · C-02/C-03 · rewriting all of classify

## Accept (amended)

1. **Contract first:** Document that `classify()` is structurally stale-blind (no prompt) and must not be used on a live rendered screen / automaton path. Name the stale `Select a game` counterexample.
2. **Enforce:** Pin(s) that fail if a live path (Session / ensure / login automaton / cockpit send that classifies a screen) calls bare `classify()` instead of `classify_screen` — or prove no such caller exists and pin a representative stale-scrollback case showing `classify` ≠ `classify_screen`.
3. **Do not** treat “add `_is_plain_timed_out_game_select` to `classify()`” as sufficient Accept by itself.
4. `pytest` green for touched tests.

## Proof

STATUS + SHA · contract wording cite · pin names · stale-scrollback divergence pin (or live-caller inventory) · pytest excerpt.

## Refs

`audit/session-classify-audit-coverage-20260726.md` C-01 · CC HEADS-UP 2026-07-26T21:16:27Z · `classify.py` `classify` vs `classify_screen`
