# WO-AICLIENT-CLEANUP-SCRIPTMISMATCH-NEVER-RAISED

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1

## Goal

`ScriptMismatch` was never raised/instantiated — mismatches already append
plain strings to `FakeTWGS.errors`. Retire the dead class.

## Changes

- Delete `ScriptMismatch` from `tests/fake_twgs.py`
- Docstrings now say "script-mismatch string on `.errors`"

## Accept

- [x] `ScriptMismatch` gone; zero remaining references
- [x] Mismatch paths still append strings to `.errors`
- live-prove: **n/a** (test harness only)

## Proof

```bash
rg -n ScriptMismatch tests/ tw2002_aiclient/   # expect 0
.venv/bin/python -m pytest tests/test_login.py tests/test_login_blank_reject.py -q -n0
```
