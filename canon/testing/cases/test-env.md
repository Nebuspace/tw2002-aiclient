---
type: Reference
title: Test Cases — Env
description: .env loader + host/port + run-dir resolution (no network).
resource: repo://tw2002-aiclient/tests/test_env.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_env.py`

_.env loader + host/port + run-dir resolution (no network)._

| Test | Blurb |
|------|-------|
| `test_load_dotenv_missing_file_returns_empty` | Load dotenv missing file returns empty. |
| `test_load_dotenv_parses_key_value_pairs` | Load dotenv parses key value pairs. |
| `test_load_dotenv_ignores_blank_lines_and_comments` | Load dotenv ignores blank lines and comments. |
| `test_load_dotenv_strips_matching_quotes` | Load dotenv strips matching quotes. |
| `test_load_dotenv_applies_values_to_os_environ` | Load dotenv applies values to os environ. |
| `test_load_dotenv_never_overwrites_existing_process_env` | Load dotenv never overwrites existing process env. |
| `test_cli_arg_wins_over_everything` | Cli arg wins over everything. |
| `test_process_env_wins_over_dotenv_file_and_profiles` | Process env wins over dotenv file and profiles. |
| `test_dotenv_file_wins_over_profiles_toml` | Dotenv file wins over profiles toml. |
| `test_profiles_toml_is_the_last_resort` | Profiles toml is the last resort. |
| `test_mixed_sources_resolve_independently_per_field` | Mixed sources resolve independently per field. |
| `test_raises_actionable_error_naming_host_var_when_unresolved` | Raises actionable error naming host var when unresolved. |
| `test_raises_actionable_error_naming_port_var_when_only_port_unresolved` | Raises actionable error naming port var when only port unresolved. |
| `test_incomplete_profile_is_treated_as_unresolved_not_a_crash` | Incomplete profile is treated as unresolved not a crash. |
| `test_malformed_env_port_raises_actionable_error_not_a_bare_valueerror` | Malformed env port raises actionable error not a bare valueerror. |
| `test_malformed_profiles_toml_port_raises_actionable_error_not_a_bare_valueerror` | Malformed profiles toml port raises actionable error not a bare valueerror. |
| `test_resolve_run_dir_defaults_to_project_rooted_run` | Resolve run dir defaults to project rooted run. |
| `test_resolve_run_dir_independent_of_cwd` | WO-P2-021 Accept: caller CWD must not move the default run/ home. |
| `test_resolve_run_dir_honors_absolute_tw_run_dir` | Resolve run dir honors absolute tw run dir. |
| `test_resolve_run_dir_honors_relative_tw_run_dir` | Resolve run dir honors relative tw run dir. |
| `test_default_run_dir_is_not_per_profile` | WO-P2-021 Accept: with TW_RUN_DIR unset there is one shared run/,. |
