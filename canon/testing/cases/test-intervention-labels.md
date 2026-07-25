---
type: Reference
title: Test Cases — test_intervention_labels
description: Shared intervention label map — single source for play + spectate.
resource: repo://tw2002-aiclient/tests/test_intervention_labels.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_intervention_labels.py`

_Shared intervention label map — single source for play + spectate._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_shared_map_covers_halt_and_stale_codes` | Shared map covers halt and stale codes. |
| `test_adapters_reexports_shared_helper` | Adapters reexports shared helper. |
| `test_play_and_spectate_compose_share_labels` | Both compose paths must resolve codes via the shared map (same strip). |
