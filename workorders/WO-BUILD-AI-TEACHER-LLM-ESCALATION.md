# WO-BUILD-AI-TEACHER-LLM-ESCALATION

**Goal:** Build the missing on-demand, human-invoked AI-teacher (`Screen
Analyze`) plumbing per `canon/engine/ai-teacher.md` — canon's own
self-identified "single biggest gap": zero code exists that reads an
unrecognized-screen escalation and returns a draft guarded rule.

**Scope:**
- `tw2002_aiclient/ai_teacher.py` — new module
- `tw2002_aiclient/teach_cli.py` — new `tw teach analyze` verb
- `tw2002_aiclient/session/cli.py` — 2-line hook only
- `tests/test_ai_teacher.py` — new
- `tests/test_cli_log.py` — closed-set verb allowlist update (`"teach"`)
- this WO file

**Out of scope:**
- **Wiring a real LLM backend.** No LLM SDK dependency (`anthropic`,
  `openai`, or similar) is added by this WO — that is a new external
  dependency requiring separate sign-off per this repo's `§8b` boundary and
  the parent coordination protocol's no-new-deps-without-sign-off rule. This
  WO builds the complete draft-and-approve plumbing behind an injectable
  `AnalyzeBackend` seam, with a `no_backend_configured` default that raises
  cleanly. A follow-up WO wires a real model once a client library is chosen
  and approved.
- Extending `STATUS_FACT_KEYS` to cover game-world guard facts (credits,
  sector, turns) — a drafted rule referencing those facts fails closed
  (`UNKNOWN`) at fire time today; unrelated pre-existing gap.
- Rewriting `rule_engine.py` / `rules/writer.py` / `alignment_gate.py` — only
  imported and used, never modified.

**Constraints:**
- Author-only: the module has **no live-send path** — it never opens a
  socket, never calls `Session.send`, never shells out. Backed by a
  structural AST/grep pin (`test_ai_teacher_module_has_no_live_send_path`,
  `test_teach_cli_module_has_no_live_send_path`), matching the existing
  family standard in `test_cockpit_analyze.py`.
- Every draft is written through `rules.writer.write_draft` only — the sole
  writer in the product, which hard-codes `approved: False` and has no
  parameter to override it. Never construct a rule/dict with
  `approved: True`.
- Ethos bound checked explicitly by the teacher itself (not just relying on
  `write_draft`'s internal refusal): `analyze_escalation` calls
  `alignment_gate.refuse_pvp_aggression_rule` as a pre-check and returns
  `{"declined": True, "reason": ...}` without writing anything if it trips —
  matching canon's "reports it will not propose a rule" requirement.
- Malformed backend output is never swallowed — `write_draft`'s strict
  `rule_from_dict` parser is the final gate; its error propagates as
  `RuleWriteError`.

**Accept:**
1. `gather_escalation_context` bundles frame + last-N ledger rows, pure/I-O
   free, windowing correct.
2. `analyze_escalation` with a valid backend draft writes an inert
   (`approved: False`) draft via `write_draft`, absent from the blessed
   rules store until a separate `promote_draft`/`tw rule approve` call.
3. `analyze_escalation` with a PvP-initiating draft declines and writes
   nothing (negative control: drafts dir empty after).
4. `no_backend_configured` raises `AITeacherBackendNotConfigured` cleanly.
5. Malformed backend output raises `RuleWriteError`, not swallowed.
6. Structural no-live-send-path pins pass on both new files.
7. `tw teach analyze` registered and dispatches correctly (closed-set verb
   inventory test updated, not bypassed).

**Proof:** `.venv/bin/python -m pytest tests/test_ai_teacher.py tests/test_rule_engine.py tests/test_rules_writer.py tests/test_cli_log.py -n0 -q` → 109 passed.
