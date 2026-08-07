# WO-WIRE-IMPERATIVE-DENYLIST-RUNTIME-CHECK

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** LOW (unused-code tick · wire_wo in-flight)  
**Depends-on:** none

## Goal

Give `IMPERATIVE_DENYLIST` a product runtime consumer — not test-only —
so authored DECISIONS vocabulary cannot drift into imperative leading
words without failing loud at app startup.

## Scope

- `tw2002_aiclient/cockpit/decisions.py` — `assert_authored_imperative_denylist`
- `tw2002_aiclient/app.py` — call at startup (with coverage-map assert)
- `tests/test_imperative_denylist_startup_wire.py`
- this WO file

## Accept

1. `assert_authored_imperative_denylist()` green on tip authored vocab.
2. `app.main` source contains the assert call (same pattern as coverage map).
3. Existing `test_fixed_vocabulary_never_uses_an_imperative_leading_word` still green.

## Proof

```bash
.venv/bin/python -m pytest tests/test_imperative_denylist_startup_wire.py tests/test_cockpit_decisions.py -q -n0
```

Live-prove: **n/a** (startup assert + offline composer pins).
