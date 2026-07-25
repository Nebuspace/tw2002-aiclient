---
type: Reference
title: Test Cases — Spectate No Send
description: WO-P4-055 lane B -- structural + behavioral proof that the product.
resource: repo://tw2002-aiclient/tests/test_spectate_no_send.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_spectate_no_send.py`

_WO-P4-055 lane B -- structural + behavioral proof that the product_

| Test | Blurb |
|------|-------|
| `test_scanner_detects_a_synthetic_send_violation` | Scanner detects a synthetic send violation. |
| `test_scanner_detects_cipher_demonstrated_bypass_aliased_import_and_getattr_reflection` | Cipher security pass (WO-P4-056 second REVISE): this EXACT source. |
| `test_scanner_detects_getattr_reflected_send_request_call` | (2) of the same Cipher finding, applied to `_iter_send_request_calls`. |
| `test_run_play_source_has_no_send_capable_call_or_symbol` | Run play source has no send capable call or symbol. |
| `test_app_module_only_ever_requests_the_status_verb` | App module only ever requests the status verb. |
| `test_allowed_predicate_still_flags_a_violation_at_a_different_function` | (1): an ordinary send-capable call OUTSIDE the two adjudicated. |
| `test_attach_allowlist_is_single_site_not_shape_wide` | Consolidated regression pin (Samantha REVISE, WO-P4-056) -- the. |
| `test_play_shell_screen_class_has_no_send_capable_call_or_symbol` | Play shell screen class has no send capable call or symbol. |
| `test_screens_module_has_no_send_capable_call_or_symbol` | Belt-and-suspenders beyond the class-scoped guard above: also bans. |
| `test_play_shell_screen_entry_state_is_app_hold_and_owns_no_send_path` | THE CANARY -- re-justified, deliberately NOT silenced (WO-ENTRY-APP-. |
| `test_watchfeed_module_has_no_send_capable_call_or_symbol` | Watchfeed module has no send capable call or symbol. |
| `test_cockpit_package_has_no_send_capable_call_or_symbol` | Cockpit package has no send capable call or symbol. |
| `test_run_play_drives_only_subscribe_and_status_writes` | Drives ``app. |
