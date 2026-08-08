# WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION

**Goal (re-scoped from a build to a doc-accuracy fix):** The queue row's
premise was that replay-side parameter substitution already exists
(`_apply_params`, only missing the capture-time generation step). Verify-
first found that premise wrong: `_apply_params` does not exist anywhere in
tip — grep-confirmed zero hits in product code. `loops/player.py`'s
`replay_loop` sends `step.input` to `session.send_and_confirm` **verbatim**,
with no substitution call site at all. So the real gap is bigger than the
row stated: parameterization exists on **neither** the capture side nor the
replay side — it is pure target-vision prose in `macros.md` today.

**Scope:**
- `canon/engine/macros.md` — Parameterization section + its Code divergence
  note corrected to state neither side is built (was: replay-side only)
- this WO file

**Out of scope:**
- Building either the capture-time numeric-token-detection step OR a
  replay-side substitution mechanism. Given the corrected scope is now a
  two-sided feature (not the one-sided capture step the row assumed), and
  building a live parameter-binding mechanism touches the macro replay
  format + `tw record`/`tw replay` CLI contract, this is bigger than a
  single-pass build and deserves its own properly-scoped WO once triaged —
  not assumed into this doc-accuracy pass.

**Constraints:** every claim in the corrected doc text is grep-verified
against `tw2002_aiclient/loops/player.py` and the wider tree, not inferred
from the old (wrong) doc wording.

**Accept:**
1. `macros.md`'s Parameterization section accurately states target-vision
   vs. current-tip status (neither side built), replacing the stale
   "replay-side only" claim.
2. No code changed; existing macro/loop test coverage unaffected.
3. The actual build (both capture-time detection and replay-side
   substitution) is left as clearly-flagged future work, not silently
   built partially against the corrected-but-still-incomplete premise.

**Proof:** `.venv/bin/python -m pytest tests/test_loop_player.py tests/test_loop_recorder.py -n0 -q` → 116 passed (docs-only change, suite unaffected — run for context confirmation only).
