# WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION-2

**Goal:** Build the two-sided feature that
`WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION` (the "-1" doc-accuracy pass)
found missing on both sides: numeric macro parameterization real on capture
AND replay, per `canon/engine/macros.md` §Parameterization's target vision.

**Scope:**
- `tw2002_aiclient/loops/loader.py` — shared `{name}` placeholder syntax
  (`is_valid_param_name`, `param_placeholder_name`), `Loop.params` field
  (immutable `MappingProxyType`, defaults to `{}`), `_validate_params`
- `tw2002_aiclient/loops/recorder.py` — `LoopRecorder.step(..., param=...)`:
  opt-in capture of a numeric step's literal value into a named recorded
  default; `document()` writes `params` only when non-empty
- `tw2002_aiclient/loops/player.py` — `_resolve_param` / `_unbound_params` /
  `_apply_params`; `replay_loop(..., params=...)` resolves every
  placeholder immediately before the send it gates, validating all steps'
  placeholders resolvable **at entry**, before the first observation
- `tw2002_aiclient/session/cli.py` — `cmd_record`'s manifest gains a
  per-step `"param"` key wired to `LoopRecorder.step(param=...)`
- `canon/engine/macros.md` — Code divergence note synced to the new tip
  reality (both sides now built)
- Tests: `tests/test_loop_loader.py`, `tests/test_loop_recorder.py`,
  `tests/test_loop_player.py`, `tests/test_cli_record.py`
- this WO file

**Out of scope (untouched, per hub instruction — other 7 tranche items
already merged):**
- `tw2002_aiclient/session/autoloop.py` — no `params` wiring added; an
  autoloop macro continues to use its recorded defaults exactly as before,
  and `replay_loop`'s new `params` keyword defaults to `None` so every
  existing call site (autoloop, rules, action_safety, cockpit/panic,
  protocol.py) is unaffected without modification
- a live `tw replay --param name=value` CLI verb — no such verb exists on
  tip today; this WO wires the library function's `params=` argument and
  the capture-side manifest, not a new CLI surface
- a live `tw attach`→recorder bridge (explicitly out of scope per the
  existing recorder docstring; unrelated to parameterization)

**Constraints:** invariants preserved unchanged — start-anchor (checked
after the gate, same as before), send-and-confirm (every step, resolved or
not, still counted/traced/halts identically on an unconfirmed send),
never-auto (the money-prompt gate fires before any send regardless of
whether the pending step's input would resolve). No new dependencies. No
secrets. Commit only explicit paths.

**Design decisions (surfaced, not silently assumed):**
1. **Explicit opt-in, never inference.** `LoopRecorder.step`'s `param`
   argument is the caller's explicit choice (the manifest's `"param"` key),
   the same shape `confirm_exact` already uses — this module never guesses
   which step is "the quantity."
2. **Numeric-only, matching canon's own examples.** `param=` requires
   all-digit `keystrokes`; a non-digit value is refused rather than
   generalizing an arbitrary command letter into something a caller could
   rebind into anything.
3. **Document-level defaults, not per-step schema growth.** `params` is a
   name → default-keystrokes map on the document/`Loop`, so a step's
   `input` stays a simple string (`"{qty}"` or a literal) — no per-step
   binding schema.
4. **Fail-closed, checked once for the whole macro at entry.** An
   unresolvable placeholder raises `ValueError` at `replay_loop` entry
   (mirroring the existing `floor`/`turn_budget` port-capability checks),
   never lazily at the send that would need it — discovering a missing
   parameter at step 5 would mean steps 0-4 already spent real turns and
   credits on a run that can never finish.
5. **Override precedence.** An explicit `replay_loop(params=...)` entry
   outranks the macro's own recorded default; omitting `params` entirely
   replays exactly as if the macro had none.

**Accept:**
1. Capture: `LoopRecorder.step(keystrokes, screen, param="qty")` on numeric
   `keystrokes` writes step `input == "{qty}"` and records `qty`'s literal
   default in `document()["params"]`; a document with zero parameterized
   steps omits the `params` key entirely (byte-identical to pre-WO shape).
2. Replay: a placeholder step resolves through `_apply_params` to the
   recorded default (or an explicit `params=` override) immediately
   before `send_and_confirm`; an unresolvable placeholder anywhere in the
   macro refuses at entry with zero bytes sent.
3. `start-anchor`, `send-and-confirm`, and `never-auto` invariants are
   unchanged — proven by tests that pin each still fires identically on a
   parameterized macro.
4. `tw record` manifest's per-step `"param"` key reaches the recorder
   through the real CLI wire (not just the recorder's own unit suite).
5. `canon/engine/macros.md`'s Code divergence note states the new reality
   (built on both sides) rather than the prior "neither side" / "replay-
   side only" wording.
6. Full test suite green (excluding pre-existing, unrelated PTY sandbox
   flakiness — see Proof).

**Proof:**

```
.venv/bin/python -m pytest tests/test_loop_player.py tests/test_loop_loader.py \
  tests/test_loop_recorder.py tests/test_cli_record.py
# 229 passed in 3.99s

.venv/bin/python -m pytest tests/
# 4 failed, 7483 passed, 1 skipped, 84 warnings in 55.95s
#   FAILED tests/test_cockpit_covermeter_pty.py::test_coverage_meter_is_visible_on_a_real_terminal
#   FAILED tests/test_cockpit_covermeter_pty.py::test_meter_reads_honest_unknown_not_a_fabricated_share
#   FAILED tests/test_cockpit_attach.py::test_ctrl_bracket_from_app_hold_is_a_no_op_state_unchanged_deliberately_ruled
#   FAILED tests/test_trade_chain_runner.py::test_start_allows_when_already_at_start_anchor
# All four are pre-existing/environmental, not caused by this WO: the two
# covermeter PTY tests fail in isolation with an os.killpg PermissionError in
# this sandbox (untouched cockpit-covermeter module); the attach/trade-chain
# pair are -n-auto parallel flakiness -- both pass individually in isolation
# (`pytest tests/test_cockpit_attach.py::... tests/test_trade_chain_runner.py::... -n0`
# -> 2 passed). None touch loops/, session/cli.py's record verb, or
# canon/engine/macros.md.
```
