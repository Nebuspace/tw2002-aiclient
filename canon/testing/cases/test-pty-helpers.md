---
type: Reference
title: Test Cases — test_pty_helpers
description: Smoke proofs for Layer-B shared harness helpers (WO-P3-HARNESS-REHAB D1 lane 2).
resource: repo://tw2002-aiclient/tests/test_pty_helpers.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_pty_helpers.py`

_Smoke proofs for Layer-B shared harness helpers (WO-P3-HARNESS-REHAB D1 lane 2)._

| Test | Blurb |
|------|-------|
| `test_helpers_do_not_import_twclient` | Layer-B consumers must stay on tw2002_aiclient / stdlib / pyte only. |
| `test_fake_client_yields_events_then_none` | Fake client yields events then none. |
| `test_pyte_helpers_locate_text_and_color_attrs` | Pyte helpers locate text and color attrs. |
| `test_set_winsize_callable` | Set winsize callable. |
| `test_claim_ctty_opt_in_is_documented_kwarg` | Resize tests opt in via claim_ctty=True; default stays off (no SIGWINCH). |
| `test_claim_ctty_delivers_sigwinch_on_master_resize` | Opt-in ctty path: TIOCSWINSZ on master → SIGWINCH in child. |
| `test_default_spawn_does_not_deliver_sigwinch` | Default start_new_session=True path stays non-ctty (030/cockpit-safe). |
