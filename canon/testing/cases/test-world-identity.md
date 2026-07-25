---
type: Reference
title: Test Cases — World Identity
description: World identity tests (TW-06) -- pure string derivation, no I/O.
resource: repo://tw2002-aiclient/tests/test_world_identity.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_world_identity.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_World identity tests (TW-06) -- pure string derivation, no I/O._

| Test | Blurb |
|------|-------|
| `test_world_id_is_deterministic_for_the_same_inputs` | World id is deterministic for the same inputs. |
| `test_world_id_is_a_string_and_filesystem_safe` | World id is a string and filesystem safe. |
| `test_world_id_host_is_case_insensitive` | Network hostnames are conventionally case-insensitive -- two. |
| `test_world_id_distinct_hosts_produce_distinct_ids` | World id distinct hosts produce distinct ids. |
| `test_world_id_distinct_game_letters_produce_distinct_ids` | World id distinct game letters produce distinct ids. |
| `test_world_id_distinct_handles_produce_distinct_ids` | The core canon requirement: two different characters registered. |
| `test_world_id_handle_case_is_preserved_not_folded` | Unlike host, handle is an exact in-game identifier where case. |
| `test_world_id_from_profile_matches_direct_call` | World id from profile matches direct call. |
| `test_world_id_from_profile_accepts_duck_typed_object` | Works against any object exposing . |
| `test_world_id_refuses_empty_or_missing_host` | World id refuses empty or missing host. |
| `test_world_id_refuses_empty_or_missing_game_letter` | World id refuses empty or missing game letter. |
| `test_world_id_refuses_empty_or_missing_handle` | World id refuses empty or missing handle. |
| `test_world_id_sanitizes_punctuation_without_colliding_common_cases` | Distinct raw handles that only differ by trailing punctuation. |
