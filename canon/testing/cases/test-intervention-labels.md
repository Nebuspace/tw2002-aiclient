---
type: Reference
title: Test Cases — Intervention Labels
description: Shared intervention label map — single source for play + spectate.
resource: repo://tw2002-aiclient/tests/test_intervention_labels.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_intervention_labels.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Shared intervention label map — single source for play + spectate._

| Test | Blurb |
|------|-------|
| `test_shared_map_covers_halt_and_stale_codes` | Shared map covers halt and stale codes. |
| `test_adapters_reexports_shared_helper` | Adapters reexports shared helper. |
| `test_play_and_spectate_compose_share_labels` | Both compose paths must resolve codes via the shared map (same strip). |
