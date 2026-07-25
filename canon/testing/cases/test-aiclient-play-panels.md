---
type: Reference
title: Test Cases — Aiclient Play Panels
description: Play-screen panel wiring from mocked ``tw status`` (WO-AICLIENT-PLAY-PANELS).
resource: repo://tw2002-aiclient/tests/test_aiclient_play_panels.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_aiclient_play_panels.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Play-screen panel wiring from mocked ``tw status`` (WO-AICLIENT-PLAY-PANELS)._

| Test | Blurb |
|------|-------|
| `test_compose_play_panels_metrics_and_goals_focus` | Compose play panels metrics and goals focus. |
| `test_compose_play_panels_focus_from_trace` | Compose play panels focus from trace. |
| `test_compose_play_panels_attention_and_log` | Compose play panels attention and log. |
| `test_compose_play_panels_attention_empty_reasons_matches_spectate` | needs_attention with no reasons → same ``! |
| `test_intervention_reason_label_known_and_passthrough` | Intervention reason label known and passthrough. |
| `test_compose_play_panels_labels_new_halt_codes` | Post INTERVENTION-AP-HALT-ATTENTION codes must label on compose. |
| `test_goals_snapshot_from_status_unknowns` | Goals snapshot from status unknowns. |
| `test_sector_from_status_prompt` | Sector from status prompt. |
