# WO-CANON-FIX-RECORD-MACRO-SECRET-REDACTION-WORDING

**Goal:** `canon/engine/macros.md:61-63` says a `--secret` send mid-capture
is "dropped, never persisted" into a replayable macro. That's inaccurate:
`cockpit/record_macro.py`'s `RecordSession.add_step` (lines ~183-217) stores
the step with `REDACTED_SENTINEL` in place of the plaintext keystroke — the
step itself is kept (preserving step-count and sequencing fidelity), only
the secret bytes are withheld. Fix the doc to match the code's actual,
arguably better, sentinel-substitution behavior.

**Scope:**
- `canon/engine/macros.md` — one paragraph, Capture section
- this WO file

**Out of scope:**
- Changing `record_macro.py`'s behavior — sentinel-substitution is correct
  and stays as-is. This is a doc-accuracy fix only.
- Auditing replay-time handling of a `REDACTED_SENTINEL` step (whether it
  can ever be pressed back literally) — unrelated to this doc's wording gap
  and not cited by the queue row.

**Constraints:**
- No credential or plaintext keystroke was ever persisted either way —
  this is a doc-accuracy gap, not a live secrets leak. No code change
  needed or made.

**Accept:**
1. `canon/engine/macros.md`'s Capture section accurately describes
   sentinel-substitution (`REDACTED_SENTINEL` placeholder step kept,
   plaintext withheld) instead of "dropped, never persisted."
2. No code touched; existing redaction test coverage unaffected.

**Proof:** `.venv/bin/python -m pytest tests/test_cockpit_record_macro.py -n0 -q` → 58 passed (docs-only change, suite unaffected).
