---
type: Reference
title: Test Cases — Name Bank
description: Name bank tests (WO-MS-4 rider) -- no network, tmp_path only.
resource: repo://tw2002-aiclient/tests/test_name_bank.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_name_bank.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Name bank tests (WO-MS-4 rider) -- no network, tmp_path only._

| Test | Blurb |
|------|-------|
| `test_real_name_bank_loads_and_is_well_formed` | Real name bank loads and is well formed. |
| `test_real_name_bank_path_points_at_tracked_data_file` | Real name bank path points at tracked data file. |
| `test_load_name_bank_missing_file_raises` | Load name bank missing file raises. |
| `test_load_name_bank_missing_section_raises` | Load name bank missing section raises. |
| `test_load_name_bank_returns_the_three_lists` | Load name bank returns the three lists. |
| `test_resolve_bank_identity_draws_all_three_when_none_explicit` | Resolve bank identity draws all three when none explicit. |
| `test_resolve_bank_identity_explicit_handle_always_wins` | Per-field, not all-or-nothing: pinning `handle` alone does NOT also. |
| `test_resolve_bank_identity_explicit_ship_and_planet_names_also_win` | Resolve bank identity explicit ship and planet names also win. |
| `test_resolve_bank_identity_per_field_override_mixes_pinned_and_drawn` | A profile may pin ONE field while leaving the others to the bank --. |
| `test_resolve_bank_identity_is_deterministic_with_a_seeded_rng` | Resolve bank identity is deterministic with a seeded rng. |
| `test_resolve_bank_identity_missing_bank_propagates_name_bank_error` | Resolve bank identity missing bank propagates name bank error. |
