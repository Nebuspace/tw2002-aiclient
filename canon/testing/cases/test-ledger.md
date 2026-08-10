---
type: Reference
title: Test Cases — test_ledger
description: Trace-Ledger tests (DESIGN-v2 §3 v2.1 item 11a, C1) -- no network, tmp_path only, never touches the real state/ directory.
resource: repo://tw2002-aiclient/tests/test_ledger.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_ledger.py`

_Trace-Ledger tests (DESIGN-v2 §3 v2.1 item 11a, C1) -- no network, tmp_path only, never touches the real state/ directory._

> **Active** on tip (default pytest collect). Historical case file once marked BANKED; tip module is collected — not among the tip **1** BANKED ignore (`test_crawl_start_protocol.py`; `test_analyze.py` BANK-DELETED). Headline inventory: **7437** tests · **308** active modules.
| Test | Blurb |
|------|-------|
| `test_snapshot_state_merges_state_parser_plus_local_cargo_extraction` | Snapshot state merges state parser plus local cargo extraction. |
| `test_snapshot_state_omits_cargo_when_absent` | Snapshot state omits cargo when absent. |
| `test_snapshot_state_prefers_you_have_credits_over_a_stale_offer_mention` | Snapshot state prefers you have credits over a stale offer mention. |
| `test_snapshot_state_falls_back_to_state_parser_when_no_you_have_line` | Snapshot state falls back to state parser when no you have line. |
| `test_snapshot_state_takes_the_last_you_have_credits_when_a_screen_shows_both` | Snapshot state takes the last you have credits when a screen shows both. |
| `test_snapshot_state_no_longer_locally_corrects_credits` | Snapshot state no longer locally corrects credits. |
| `test_extract_prompt_returns_last_meaningful_line` | Extract prompt returns last meaningful line. |
| `test_extract_prompt_redacts_a_password_entry_line` | Extract prompt redacts a password entry line. |
| `test_extract_prompt_empty_when_pre_text_blank` | Extract prompt empty when pre text blank. |
| `test_record_do_captures_the_prompt_field` | Record do captures the prompt field. |
| `test_record_do_redacts_prompt_for_secret_input_even_without_the_word_password` | Record do redacts prompt for secret input even without the word password. |
| `test_render_keystroke_blank_input_is_never_invisible` | Render keystroke blank input is never invisible. |
| `test_render_keystroke_control_byte_symbolic` | Render keystroke control byte symbolic. |
| `test_render_keystroke_backspace_symbolic` | Render keystroke backspace symbolic. |
| `test_render_keystroke_redacted_input` | Render keystroke redacted input. |
| `test_render_keystroke_highlights_normal_text` | Render keystroke highlights normal text. |
| `test_render_trail_line_renders_question_keystroke_and_result` | Render trail line renders question keystroke and result. |
| `test_render_trail_line_falls_back_to_screen_delta_when_no_reward` | Render trail line falls back to screen delta when no reward. |
| `test_compute_reward_computes_deltas_when_both_present` | Compute reward computes deltas when both present. |
| `test_compute_reward_omits_field_when_either_side_missing` | Compute reward omits field when either side missing. |
| `test_summarize_screen_delta_unchanged` | Summarize screen delta unchanged. |
| `test_summarize_screen_delta_reports_changed_lines` | Summarize screen delta reports changed lines. |
| `test_ledger_writer_append_and_read_roundtrip` | Ledger writer append and read roundtrip. |
| `test_ledger_writer_redacts_secret_input_via_append` | Ledger writer redacts secret input via append. |
| `test_record_do_defaults_actor_to_ai_and_session_fields_to_none` | Record do defaults actor to ai and session fields to none. |
| `test_record_do_accepts_explicit_actor_session_id_and_intent` | Record do accepts explicit actor session id and intent. |
| `test_record_do_accepts_actor_human` | Record do accepts actor human. |
| `test_read_entries_treats_a_pre_tw05_row_without_actor_fields_as_readable` | Read entries treats a pre tw05 row without actor fields as readable. |
| `test_read_entries_mixes_pre_and_post_tw05_rows_without_error` | Read entries mixes pre and post tw05 rows without error. |
| `test_read_entries_skips_corrupt_trailing_line` | Read entries skips corrupt trailing line. |
| `test_read_entries_missing_file_returns_empty_list` | Read entries missing file returns empty list. |
