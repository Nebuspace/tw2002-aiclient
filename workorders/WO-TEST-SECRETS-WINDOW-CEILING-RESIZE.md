# WO-TEST-SECRETS-WINDOW-CEILING-RESIZE

**Goal:** Size the `str()`-window length backstop off its measured worst case so it can fire on total-disclosure-shaped growth.

**Scope:** `tests/test_secrets_store_redaction.py` (~`:483` `len(rendered) < 200`).

**Context:** #193 measured worst real rendering **78** across 16 parametrizations; bound **200** is 2.6× that. A full 42-byte buffer as window (~120) still passes. `SENTINEL not in rendered` catches full-buffer-with-sentinel cases; length backstop is for **split**-sentinel arrangements the docstring excludes from the identity assert. Do **not** remove the assert.

**Accept:**
1. Bound ≈120 (sized off measured 78 with modest headroom).
2. Simulated 42-byte full-buffer window **fails**.
3. All 16 real parametrizations still pass.
4. Assert not removed.

**Proof:** injected window reddens; suite. live-prove `n/a`.

**Refs:** #193 F1 · CC 20:23:58Z.
