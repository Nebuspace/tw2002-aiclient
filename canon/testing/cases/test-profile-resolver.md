---
type: Reference
title: Test Cases — test_profile_resolver
description: Profile resolver.
resource: repo://tw2002-aiclient/tests/test_profile_resolver.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_profile_resolver.py`

_Profile resolver._

| Test | Blurb |
|------|-------|
| `test_resolve_catalog_only_profile_uses_server_catalog` | Resolve catalog only profile uses server catalog. |
| `test_resolve_explicit_host_port_overrides_server_catalog` | Resolve explicit host port overrides server catalog. |
| `test_resolve_neither_host_port_nor_server_raises` | Resolve neither host port nor server raises. |
| `test_resolve_missing_profile_section_raises` | Resolve missing profile section raises. |
| `test_resolve_missing_profiles_file_raises` | Resolve missing profiles file raises. |
| `test_resolve_unknown_server_catalog_key_raises` | Resolve unknown server catalog key raises. |
| `test_tw_config_dir_isolation_across_process_boundary` | Tw config dir isolation across process boundary. |
| `test_env_var_still_wins_over_profile` | Env var still wins over profile. |
| `test_env_and_credentials_agree_on_catalog_only_profile` | Env and credentials agree on catalog only profile. |
| `test_resolver_never_writes_a_secrets_file` | This resolver deals only in host/port -- confirm no secrets.json is ever created as a side effect of resolving a profile. |
