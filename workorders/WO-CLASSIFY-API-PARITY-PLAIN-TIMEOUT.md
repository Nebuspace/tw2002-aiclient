# WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT

**Status:** OPEN · READY · offline · Claude Code preferred  
**Posted:** 2026-07-26 · from `audit/session-classify-audit-coverage-20260726.md` C-01  
**Base tip:** `origin/main` (`94a29f4` or newer)

## Goal

Close the divergence where `classify_screen` runs `_is_plain_timed_out_game_select` but bare `classify()` does not — so Timed Out + Select-a-game shapes cannot silently disagree across call sites.

## Scope

- `tw2002_aiclient/session/classify.py` — align `classify()` pre-pass with `classify_screen`, **or** document + enforce “live path must use `classify_screen`” with a lint/pin that catches bare-`classify()` misuse on that shape
- Pins for parity (same fixture → same class from both entry points, or intentional single-entry-point enforcement)
- **Out:** Explore HOLD · invent new screen classes · live proves · unrelated classify narrowings (C-02/C-03 are separate WOs)

## Accept

1. Either `classify()` gains the plain-timeout pre-pass used by `classify_screen`, or callers/tests prove live path cannot use bare `classify()` for that shape and the divergence is documented as intentional with a failing pin if someone reintroduces the unsafe call pattern.
2. Pin covers Timed Out + Select-a-game fixture(s) for the chosen strategy.
3. `pytest tests/test_classify.py` (and any new pin file) green.

## Proof

STATUS + SHA · strategy chosen (align vs enforce) · pin names · pytest excerpt.

## Refs

`audit/session-classify-audit-coverage-20260726.md` C-01 · `classify.py` `classify` vs `classify_screen`
