---
type: Reference
title: Test Cases — test_game_knowledge_learned_rules
description: Learned-rule store tests — offline, tmp_path only.
resource: repo://tw2002-aiclient/tests/test_game_knowledge_learned_rules.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_game_knowledge_learned_rules.py`

_Learned-rule store tests — offline, tmp_path only._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_new_knowledge_includes_learned_rules` | New knowledge includes learned rules. |
| `test_upsert_learned_rule_round_trip` | Upsert learned rule round trip. |
| `test_upsert_learned_rule_idempotent_updates` | Upsert learned rule idempotent updates. |
| `test_list_learned_rules_for_state` | List learned rules for state. |
| `test_upsert_learned_rule_validation` | Upsert learned rule validation. |
| `test_load_defaults_learned_rules_on_legacy_file` | Load defaults learned rules on legacy file. |
