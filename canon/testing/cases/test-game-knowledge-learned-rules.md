---
type: Reference
title: Test Cases — Game Knowledge Learned Rules
description: Learned-rule store tests — offline, tmp_path only.
resource: repo://tw2002-aiclient/tests/test_game_knowledge_learned_rules.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_game_knowledge_learned_rules.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Learned-rule store tests — offline, tmp_path only._

| Test | Blurb |
|------|-------|
| `test_new_knowledge_includes_learned_rules` | New knowledge includes learned rules. |
| `test_upsert_learned_rule_round_trip` | Upsert learned rule round trip. |
| `test_upsert_learned_rule_idempotent_updates` | Upsert learned rule idempotent updates. |
| `test_list_learned_rules_for_state` | List learned rules for state. |
| `test_upsert_learned_rule_validation` | Upsert learned rule validation. |
| `test_load_defaults_learned_rules_on_legacy_file` | Load defaults learned rules on legacy file. |
