---
type: Reference
title: Test Cases — Login
description: Login Automaton end-to-end proof (WO-P2-023): drives the REAL.
resource: repo://tw2002-aiclient/tests/test_login.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_login.py`

_Login Automaton end-to-end proof (WO-P2-023): drives the REAL_

| Test | Blurb |
|------|-------|
| `test_returning_login_sends_saved_password_once_and_reaches_main_command` | Returning login sends saved password once and reaches main command. |
| `test_returning_slow_transition_reaches_main_command` | Mack HIGH regression guard: a legitimate RETURNING login whose. |
| `test_new_registration_completes_and_saves_generated_password_before_send` | New registration completes and saves generated password before send. |
| `test_registration_refused_raises_before_any_char_create_send` | Registration refused raises before any char create send. |
| `test_wrong_saved_password_fails_fast_never_reaches_main_command` | Wrong saved password fails fast never reaches main command. |
