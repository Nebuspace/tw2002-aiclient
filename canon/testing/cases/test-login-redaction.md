---
type: Reference
title: Test Cases — Login Redaction
description: Cipher security gate (2026-07-20): sentinel-password redaction proof.
resource: repo://tw2002-aiclient/tests/test_login_redaction.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_login_redaction.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Cipher security gate (2026-07-20): sentinel-password redaction proof_

| Test | Blurb |
|------|-------|
| `test_green_sentinel_absent_from_log_transcript_with_redaction_on` | Green sentinel absent from log transcript with redaction on. |
| `test_green_sentinel_absent_from_settle_confirm_buffer_reads` | Green sentinel absent from settle confirm buffer reads. |
| `test_login_password_step_passes_no_confirm_prompt_to_send_and_confirm` | Point 4 of the gate, proven directly against the real `_decide`. |
| `test_green_sentinel_absent_from_run_login_success_return_value` | Green sentinel absent from run login success return value. |
| `test_green_sentinel_absent_from_login_error_text_on_retry_exhaustion` | Forces `password_retries_exhausted` with the sentinel active as the. |
| `test_green_sentinel_absent_from_automaton_stuck_error_text` | A DIFFERENT failure shape: the password send is confirmed, but the. |
| `test_falsification_bypassed_redaction_leaks_sentinel_into_log_RED` | Temporarily patches `TelnetConnection. |
| `test_falsification_confirms_default_send_text_still_redacts` | Sanity bookend to the RED test above: with NO monkeypatch, the. |
| `test_demonstrates_plain_grep_without_dash_a_is_a_false_negative_risk` | NOT a test of this project's code -- a grounding/documentation test. |
| `test_green_sentinel_absent_via_grep_a_non_vacuous_check` | The real login-redaction transcript, re-verified with the. |
| `test_green_sentinel_absent_from_ledger_across_real_dispatch_ensure` | Empirical (not merely static) proof of sink (d): drives the REAL. |
| `test_ledger_record_do_redacts_secret_input_and_prompt` | Floor check on ledger. |
| `test_falsification_ledger_would_leak_sentinel_if_secret_flag_forgotten_RED` | Falsification for the LEDGER sink specifically -- the one the hub. |
