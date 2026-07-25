---
type: Reference
title: Test Cases — Ensure Protocol
description: Thin proofs for session/protocol.
resource: repo://tw2002-aiclient/tests/test_ensure_protocol.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_ensure_protocol.py`

_Thin proofs for session/protocol.py ``ensure`` dispatch._

| Test | Blurb |
|------|-------|
| `test_ensure_already_there_fast_path` | Default FakeAttachSession screen classifies main_command → steps=0. |
| `test_ensure_missing_profile` | Ensure missing profile. |
| `test_ensure_profile_not_found` | Ensure profile not found. |
| `test_ensure_concurrent_control_lock_returns_controller_busy` | Ensure concurrent control lock returns controller busy. |
| `test_ensure_refuses_while_human_attached` | Ensure refuses while human attached. |
| `test_ensure_refuses_while_spectate` | Ensure refuses while spectate. |
