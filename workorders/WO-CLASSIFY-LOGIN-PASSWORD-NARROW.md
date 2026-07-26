# WO-CLASSIFY-LOGIN-PASSWORD-NARROW

**Status:** OPEN · READY · offline · Cursor preferred  
**Posted:** 2026-07-26 · from `audit/session-classify-audit-coverage-20260726.md` C-02  
**Base tip:** `origin/main` (`3fa3493` or newer)

## Goal

Tighten the `login_password` gate (`classify.py` bare `password` substring) so help/utility prompt lines containing the word cannot steal the class when they are the active prompt — without breaking the login automaton fixtures.

## Scope

- `tw2002_aiclient/session/classify.py` — `_GATE_ANCHORS` / `login_password` pattern
- Pins in `tests/test_classify.py` (or new pin file): false-positive refuse + true login password still classifies
- **Out:** Explore HOLD · live proves · C-01 (CC lane) · C-03 pause_key · invent classes · credentials redesign

## Accept

1. A prompt that merely contains the word `password` in non-login chrome (e.g. help/utility) does **not** classify as `login_password` when it is the active prompt line.
2. Real login password prompts still classify as `login_password` (existing fixtures stay green).
3. Docstring/comment names the false-positive hazard.
4. `pytest tests/test_classify.py` green (plus any new pins).

## Proof

STATUS + SHA · pin names · before/after class on the false-positive fixture · pytest excerpt.

## Refs

`audit/session-classify-audit-coverage-20260726.md` C-02 · `classify.py` gate anchors
