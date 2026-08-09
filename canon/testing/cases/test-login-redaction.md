---
type: Reference
title: Test Cases — test_login_redaction
description: Cipher security gate (2026-07-20): sentinel-password redaction proof across the TW-02 `send_and_confirm` login/password swap (a2e99f6).
resource: repo://tw2002-aiclient/tests/test_login_redaction.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_login_redaction.py`

_Cipher security gate (2026-07-20): sentinel-password redaction proof across the TW-02 `send_and_confirm` login/password swap (a2e99f6)._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **2** BANKED ignores (`test_analyze.py`, `test_crawl_start_protocol.py`). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_green_sentinel_absent_from_log_transcript_with_redaction_on` | Green sentinel absent from log transcript with redaction on. |
| `test_green_sentinel_absent_from_settle_confirm_buffer_reads` | Green sentinel absent from settle confirm buffer reads. |
| `test_login_password_step_passes_no_confirm_prompt_to_send_and_confirm` | Login password step passes no confirm prompt to send and confirm. |
| `test_green_sentinel_absent_from_run_login_success_return_value` | Green sentinel absent from run login success return value. |
| `test_green_sentinel_absent_from_login_error_text_on_retry_exhaustion` | Green sentinel absent from login error text on retry exhaustion. |
| `test_green_sentinel_absent_from_automaton_stuck_error_text` | Green sentinel absent from automaton stuck error text. |
| `test_falsification_bypassed_redaction_leaks_sentinel_into_log_RED` | Falsification bypassed redaction leaks sentinel into log RED. |
| `test_falsification_confirms_default_send_text_still_redacts` | Falsification confirms default send text still redacts. |
| `test_demonstrates_plain_grep_without_dash_a_is_a_false_negative_risk` | Demonstrates plain grep without dash a is a false negative risk. |
| `test_green_sentinel_absent_via_grep_a_non_vacuous_check` | Green sentinel absent via grep a non vacuous check. |
| `test_green_sentinel_absent_from_ledger_across_real_dispatch_ensure` | Green sentinel absent from ledger across real dispatch ensure. |
| `test_ledger_record_do_redacts_secret_input_and_prompt` | Ledger record do redacts secret input and prompt. |
| `test_falsification_ledger_would_leak_sentinel_if_secret_flag_forgotten_RED` | Falsification for the LEDGER sink specifically -- the one the hub flagged as most likely to be missed. |
