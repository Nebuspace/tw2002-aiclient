---
type: Reference
title: Test Cases — test_probe
description: WO-MS-3 probe tests — classification, polite envelope, L0/L1 invariants.
resource: repo://tw2002-aiclient/tests/test_probe.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_probe.py`

_WO-MS-3 probe tests — classification, polite envelope, L0/L1 invariants._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_classify_twgs_direct` | Classify twgs direct. |
| `test_classify_bbs` | Classify bbs. |
| `test_classify_mystic_bbs` | MS-3b: Mystic banner → bbs (was protocol-fail without this anchor). |
| `test_classify_wildcat_bbs` | MS-3b: Wildcat banner → bbs. |
| `test_classify_protocol_fail` | Classify protocol fail. |
| `test_l0_probe_sends_only_iac` | Harness: L0 path may sendall only what TelnetHandler queues (IAC). |
| `test_l1_sends_exactly_one_cr_at_twgs_prompt` | L1 sends exactly one cr at twgs prompt. |
| `test_l1_refuses_cr_on_bbs_banner` | L1 refuses cr on bbs banner. |
| `test_non_telnet_transport_skipped` | Non telnet transport skipped. |
| `test_unreachable` | Unreachable. |
| `test_l0_source_has_no_bare_cr_send` | Static guard: L0 helper `_send_iac_only` is the only TX on L0 reads; bare `sendall(b"\r")` appears only under the menu/L1 branch. |
| `test_patch_catalog_status` | Patch catalog status. |
