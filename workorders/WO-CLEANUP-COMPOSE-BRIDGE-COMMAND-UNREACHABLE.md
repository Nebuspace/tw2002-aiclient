# WO-CLEANUP-COMPOSE-BRIDGE-COMMAND-UNREACHABLE

**Goal:** `compose_bridge_command()` in `draft_approve.py` had zero product
callers — its own docstring called it a "CLI fallback" for operators who
"leave the client," but nothing in `app.py`, the CLI, or canon ever printed
or otherwise surfaced its output, and its dedicated test in
`test_play_rule_identity.py` (`test_run_play_wires_bridge_write_and_promote`)
affirmatively pinned that it must **not** be called from `_run_play`. Retire
the dead composer rather than invent a caller for it.

**Scope:**
- `tw2002_aiclient/cockpit/draft_approve.py` — delete `compose_bridge_command`
- `tests/test_draft_approve_bridge.py` — drop the import and the three tests
  that existed solely to exercise the composer
  (`test_the_command_carries_the_observed_screen_and_leaves_the_rest_blank`,
  `test_the_command_never_raises_and_degrades_to_a_question_mark`,
  `test_the_command_is_the_one_the_cli_actually_accepts`); refresh a stale
  docstring reference in `test_the_cockpit_gate_is_actually_wired_to_the_bridge_hint`
- `tests/test_play_rule_identity.py` — drop the now-meaningless
  `assert "compose_bridge_command" not in called` line from
  `test_run_play_wires_bridge_write_and_promote` (asserting a deleted name is
  never called is vacuously true forever and adds no signal); the rest of
  that test's positive wiring pins (`bridge_to_kernel_document`,
  `write_draft`, `promote_draft`, `begin_rule_identity`,
  `compose_rule_blessed_line`) are untouched
- this WO file

**Out of scope:**
- The real `tw rule draft --screen … --rule-id … --do … --priority …` CLI
  verb (`tw2002_aiclient/rules/cli.py::cmd_rule_draft`), which the deleted
  composer merely echoed as a string — that verb is live, tested elsewhere,
  and stays.
- `create_identity_session` / `bridge_to_kernel_document` /
  `promote_to_approved` — Play's live typed-entry path (WO-PLAY-RULE-IDENTITY),
  fully wired and unaffected.

**WIRE vs RETIRE — decision and evidence:**
Grepped the whole tree (`canon/`, `workorders/`, docs) for "bridge command" /
`compose_bridge_command`: zero hits outside the function's own definition and
its two test files — no documented surface (help text, CLI subcommand,
another screen) ever called for this hint to be printed. Read `app.py`'s
`_run_play`: the `rule_identity_cancel` branch (the one place a "leave the
client and use the shell instead" hint would plausibly belong) just sets a
status line and returns — no call to the composer, and
`test_run_play_wires_bridge_write_and_promote` explicitly pins that
`compose_bridge_command` must **not** appear in `_run_play`'s call set. That
pin predates this WO and was written on purpose (WO-PLAY-RULE-IDENTITY
retired the CLI-only path in favor of typed entry) — wiring the composer in
now would mean deliberately breaking a test the team wrote to keep it out.
With no discovered surface asking for it and an existing test forbidding its
only plausible wiring point, **RETIRE**.

**Accept:**
1. `compose_bridge_command` no longer exists in `draft_approve.py`.
2. No remaining product or test code imports or calls it (verified by grep).
3. `test_play_rule_identity.py`'s wiring pin still positively asserts
   `bridge_to_kernel_document`, `write_draft`, `promote_draft`,
   `begin_rule_identity`, and `compose_rule_blessed_line` are called from
   `_run_play` — the vacuous negative assertion is dropped, the load-bearing
   positive assertions are untouched.
4. The real `tw rule draft` CLI verb is untouched and still covered by its
   own tests in `tests/test_cli_rule_wiring.py` — this WO only removes the
   disconnected string composer, not the working command it echoed.

**Proof:** `.venv/bin/python -m pytest tests/test_draft_approve*.py tests/test_play_rule_identity.py -n0 -q` → 42 passed. `grep -rn "compose_bridge_command" --include=*.py .` → only the historical docstring mention and the still-valid negative-control assertion in `test_draft_approve_bridge.py` (`"compose_bridge_command_that_does_not_exist" not in called`, unrelated to the deleted symbol). Full `tests/` sweep (`-n auto`) shows no new failures introduced — the two pre-existing `test_cockpit_covermeter_pty.py` failures are unrelated PTY/live-terminal tests with no reference to `draft_approve`.
