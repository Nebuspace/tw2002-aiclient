---
type: Reference
title: Test Cases — test_world_identity
description: World identity.
resource: repo://tw2002-aiclient/tests/test_world_identity.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_world_identity.py`

_World identity._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_world_id_is_deterministic_for_the_same_inputs` | World id is deterministic for the same inputs. |
| `test_world_id_is_a_string_and_filesystem_safe` | World id is a string and filesystem safe. |
| `test_world_id_host_is_case_insensitive` | Network hostnames are conventionally case-insensitive -- two profiles differing only in host casing must resolve to the SAME world, not two spurious ones. |
| `test_world_id_distinct_hosts_produce_distinct_ids` | World id distinct hosts produce distinct ids. |
| `test_world_id_distinct_game_letters_produce_distinct_ids` | World id distinct game letters produce distinct ids. |
| `test_world_id_distinct_handles_produce_distinct_ids` | World id distinct handles produce distinct ids. |
| `test_world_id_handle_case_is_preserved_not_folded` | Unlike host, handle is an exact in-game identifier where case can be a real distinction -- not free-form user text to normalize. |
| `test_world_id_from_profile_matches_direct_call` | World id from profile matches direct call. |
| `test_world_id_from_profile_accepts_duck_typed_object` | Works against any object exposing .host/.game_letter/.handle -- not hard-wired to credentials.Profile specifically. |
| `test_world_id_refuses_empty_or_missing_host` | World id refuses empty or missing host. |
| `test_world_id_refuses_empty_or_missing_game_letter` | World id refuses empty or missing game letter. |
| `test_world_id_refuses_empty_or_missing_handle` | World id refuses empty or missing handle. |
| `test_world_id_sanitizes_punctuation_without_colliding_common_cases` | World id sanitizes punctuation without colliding common cases. |
