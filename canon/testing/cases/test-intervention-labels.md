---
type: Reference
title: Test Cases — test_intervention_labels
description: REMOVED — historical inventory; tip module absent. Shared intervention label map — single source for play + spectate.
resource: repo://tw2002-aiclient/tests/test_intervention_labels.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-09T09:15:46Z
---

# Test Cases — `tests/test_intervention_labels.py`

_Shared intervention label map — single source for play + spectate._

> **REMOVED** — module absent on tip (not merely pytest-ignored). Catalogued for completeness (historical inventory).
| Test | Blurb |
|------|-------|
| `test_shared_map_covers_halt_and_stale_codes` | Shared map covers halt and stale codes. |
| `test_adapters_reexports_shared_helper` | Adapters reexports shared helper. |
| `test_play_and_spectate_compose_share_labels` | Both compose paths must resolve codes via the shared map (same strip). |
