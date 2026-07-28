---
type: Reference
title: Test Cases — test_world_model_landmarks
description: landmarks unions rather than replaces (WO-WM-LANDMARKS-WRITE P1).
resource: repo://tw2002-aiclient/tests/test_world_model_landmarks.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-28T15:33:53Z
---

# Test Cases — `tests/test_world_model_landmarks.py`

_Nothing the trainer can read says "there is positively no landmark here" — a sector
display that omits StarDock is **silence, not a denial**. Under replace semantics the
next ordinary write would erase what an earlier observation found, and the erasure is
indistinguishable from never having found it._

| Test | Blurb |
|------|-------|
| `test_a_later_write_cannot_clear_a_landmark` | The load-bearing rule: an empty list must not erase StarDock. |
| `test_a_later_write_with_a_different_landmark_keeps_both` | Observations accumulate. |
| `test_an_absent_landmarks_key_still_leaves_them_untouched` | The pre-existing additive half, pinned so the union is not what accidentally provides it. |
| `test_the_reader_finds_it_after_an_erasing_write` | End to end through `find_landmark_sectors`, the real consumer. |
| `test_dedup_is_casefold_because_the_reader_casefolds` | The record must not disagree with lookups made against it. |
| `test_existing_order_is_stable_and_new_tokens_append` | Records stay stable and diffable across runs. |
| `test_junk_never_corrupts_the_set` | Non-name entries could only ever fail a lookup; dropped, not stored. |
| `test_a_bare_string_is_refused_not_shredded_per_character` | A string is iterable — iterating it would store one landmark per character. |
| `test_the_first_write_still_records` | Negative control: a union returning existing unchanged would pass every "cannot clear" test. |
| `test_other_fields_still_REPLACE` | A union leaking into `warps` would plan hops that do not exist. |
| `test_write_from_state_still_refuses_landmarks` | The raw per-visit state read stays unable to touch landmarks. |
