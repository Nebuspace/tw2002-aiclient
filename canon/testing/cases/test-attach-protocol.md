---
type: Reference
title: Test Cases — test_attach_protocol
description: Attach control-lock handoff over a real unix socket + FakeAttachSession.
resource: repo://tw2002-aiclient/tests/test_attach_protocol.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_attach_protocol.py`

_Attach control-lock handoff over a real unix socket + FakeAttachSession._

| Test | Blurb |
|------|-------|
| `test_do_succeeds_when_nobody_is_attached` | Do succeeds when nobody is attached. |
| `test_status_reports_mode_app_by_default` | Status reports mode app by default. |
| `test_attach_takes_the_lock_and_rejects_ai_do_and_send` | Attach takes the lock and rejects ai do and send. |
| `test_attach_forwards_raw_keystrokes_to_the_session` | Attach forwards raw keystrokes to the session. |
| `test_detach_releases_the_lock_so_ai_can_send_again` | Detach releases the lock so ai can send again. |
| `test_second_attach_is_rejected_while_one_is_active` | Second attach is rejected while one is active. |
| `test_attach_succeeds_again_after_first_session_detaches` | Attach succeeds again after first session detaches. |
