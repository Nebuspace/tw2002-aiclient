---
type: Reference
title: Test Cases — Transcript Tail
description: Session-side redacted transcript ring buffer (WO-P3-041 LOGS band).
resource: repo://tw2002-aiclient/tests/test_transcript_tail.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_transcript_tail.py`

_Session-side redacted transcript ring buffer (WO-P3-041 LOGS band)._

| Test | Blurb |
|------|-------|
| `test_session_send_non_secret_appends_direction_and_sender_tagged_line` | Session send non secret appends direction and sender tagged line. |
| `test_session_send_secret_appends_only_the_marker_never_the_text` | Session send secret appends only the marker never the text. |
| `test_session_send_raw_non_secret_appends_per_keystroke_sender_tagged_line` | Session send raw non secret appends per keystroke sender tagged line. |
| `test_session_send_raw_secret_prompt_appends_only_markers_never_cleartext` | Session send raw secret prompt appends only markers never cleartext. |
| `test_falsification_broken_secret_classifier_would_leak_into_tail` | Mandatory falsification for the send_raw() secret path: patches. |
| `test_status_verb_carries_log_tail_from_a_real_session` | Status verb carries log tail from a real session. |
| `test_status_verb_log_tail_defaults_empty_list_without_a_tail_attribute` | Status verb log tail defaults empty list without a tail attribute. |
| `test_end_to_end_sentinel_password_never_reaches_status_response` | End to end sentinel password never reaches status response. |
| `test_ring_bounds_overflow_drops_oldest_order_preserved_newest_last` | Ring bounds overflow drops oldest order preserved newest last. |
| `test_default_maxlen_matches_tail_max_constant` | Default maxlen matches tail max constant. |
| `test_append_redacted_inserts_marker_mirroring_logging_util_wording` | Append redacted inserts marker mirroring logging util wording. |
| `test_append_redacted_custom_note_still_only_a_note_no_payload_param` | Append redacted custom note still only a note no payload param. |
| `test_falsification_append_line_is_not_itself_the_guard` | `append_line()` has no notion of "secret" -- it stores exactly. |
| `test_snapshot_isolation_mutating_returned_list_does_not_touch_ring` | Snapshot isolation mutating returned list does not touch ring. |
