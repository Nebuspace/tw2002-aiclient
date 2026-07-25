---
type: Reference
title: Test Cases — Credentials
description: Secure credential store tests (DESIGN-v2 B2) — no network, tmp_path.
resource: repo://tw2002-aiclient/tests/test_credentials.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_credentials.py` — **BANKED** (excluded from default test run; awaiting rehabilitation)

> **BANKED** — this module is excluded from the default pytest run via `pytest.ini --ignore`. Cases are catalogued for completeness; they will not run until a rehabilitation work order rewrites or removes the ignore.

_Secure credential store tests (DESIGN-v2 B2) — no network, tmp_path_

| Test | Blurb |
|------|-------|
| `test_load_profile_reads_required_fields` | Load profile reads required fields. |
| `test_load_profile_honors_optional_ship_planet_overrides` | Load profile honors optional ship planet overrides. |
| `test_load_profile_missing_name_raises` | Load profile missing name raises. |
| `test_load_profile_incomplete_raises` | Load profile incomplete raises. |
| `test_allow_register_defaults_false_for_every_pre_existing_profile_shape` | Allow register defaults false for every pre existing profile shape. |
| `test_allow_register_true_is_read_from_toml` | Allow register true is read from toml. |
| `test_missing_handle_raises_unless_allow_register_is_set` | A normal profile still requires `handle` exactly as before this. |
| `test_missing_handle_is_allowed_when_allow_register_is_true` | Missing handle is allowed when allow register is true. |
| `test_profile_explicit_flags_reflect_what_the_caller_actually_passed` | The name-bank rider (twclient/name_bank. |
| `test_list_profiles` | List profiles. |
| `test_corrupt_profiles_toml_raises_credential_error_not_toml_decode` | WO-PROFILES-TOML-PARSE-HARDEN: tomllib failures must surface as. |
| `test_load_profile_returns_last_good_profile_on_transient_parse_error` | Mid-write profiles. |
| `test_load_profile_parse_error_without_cache_still_raises` | Load profile parse error without cache still raises. |
| `test_get_password_returns_none_when_nothing_saved` | Get password returns none when nothing saved. |
| `test_save_then_get_password_roundtrips` | Save then get password roundtrips. |
| `test_secrets_file_is_chmod_600` | Secrets file is chmod 600. |
| `test_env_var_takes_precedence_over_secrets_file` | Env var takes precedence over secrets file. |
| `test_env_var_name_sanitizes_profile_name` | Env var name sanitizes profile name. |
| `test_generated_password_is_short_alnum_and_csprng_varies` | Generated password is short alnum and csprng varies. |
| `test_save_password_never_writes_plaintext_to_profiles_toml` | The password must land ONLY in the secrets file, never anywhere. |
| `test_secrets_json_shape` | Secrets json shape. |
| `test_save_password_preserves_other_profiles` | Save password preserves other profiles. |
| `test_autopilot_defaults_false` | Autopilot defaults false. |
| `test_autopilot_key_preferred_over_autonomous` | Autopilot key preferred over autonomous. |
| `test_legacy_autonomous_still_enables_autopilot` | Legacy autonomous still enables autopilot. |
| `test_set_profile_autopilot_write_back` | Set profile autopilot write back. |
| `test_create_profile_appends_autopilot` | Create profile appends autopilot. |
| `test_list_profile_summaries` | List profile summaries. |
