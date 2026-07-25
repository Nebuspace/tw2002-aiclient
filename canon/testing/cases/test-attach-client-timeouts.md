---
type: Reference
title: Test Cases — Attach Client Timeouts
description: AttachInputConn socket-op timeouts (HARDEN-ATTACH).
resource: repo://tw2002-aiclient/tests/test_attach_client_timeouts.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_attach_client_timeouts.py`

_AttachInputConn socket-op timeouts (HARDEN-ATTACH)._

| Test | Blurb |
|------|-------|
| `test_connect_returns_within_bound_against_a_fully_silent_daemon` | Connect returns within bound against a fully silent daemon. |
| `test_send_key_returns_within_bound_after_daemon_goes_silent_post_connect` | Send key returns within bound after daemon goes silent post connect. |
| `test_close_is_safe_after_a_timed_out_connect` | Close is safe after a timed out connect. |
| `test_close_is_safe_after_a_timed_out_send_key` | Close is safe after a timed out send key. |
| `test_timeout_armed_happy_path_still_attaches_and_sends_normally` | Regression: the timeout must not slow down or break the real. |
