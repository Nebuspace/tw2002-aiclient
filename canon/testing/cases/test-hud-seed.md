---
type: Reference
title: Test Cases — Hud Seed
description: WO-HUD-CREDITS-TURNS-JOIN — cold-join I-probe + sticky turns.
resource: repo://tw2002-aiclient/tests/test_hud_seed.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_hud_seed.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_WO-HUD-CREDITS-TURNS-JOIN — cold-join I-probe + sticky turns._

| Test | Blurb |
|------|-------|
| `test_seed_hud_skips_probe_when_already_known` | Seed hud skips probe when already known. |
| `test_seed_hud_defers_i_on_fighter_option_even_when_stats_unknown` | I on Option? |
| `test_seed_hud_force_reprobes_even_when_already_known` | WO-AP-HUD-REFRESH: force=True sends I even when credits/turns known. |
