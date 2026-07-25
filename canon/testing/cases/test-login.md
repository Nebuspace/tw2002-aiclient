---
type: Reference
title: Test Cases — test_login
description: Login.
resource: repo://tw2002-aiclient/tests/test_login.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_login.py`

_Login._

| Test | Blurb |
|------|-------|
| `test_returning_login_sends_saved_password_once_and_reaches_main_command` | Returning login sends saved password once and reaches main command. |
| `test_returning_slow_transition_reaches_main_command` | Returning slow transition reaches main command. |
| `test_new_registration_completes_and_saves_generated_password_before_send` | New registration completes and saves generated password before send. |
| `test_registration_refused_raises_before_any_char_create_send` | Registration refused raises before any char create send. |
| `test_wrong_saved_password_fails_fast_never_reaches_main_command` | Wrong saved password fails fast never reaches main command. |
