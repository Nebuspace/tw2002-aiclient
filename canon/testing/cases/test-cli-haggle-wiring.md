---
type: Reference
title: Test Cases — test_cli_haggle_wiring
description: `tw haggle` CLI verb wiring -- argparse only (dispatch itself needs a live daemon and is exercised at the protocol layer instead, see tests/test_protocol_haggle.py).
resource: repo://tw2002-aiclient/tests/test_cli_haggle_wiring.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_cli_haggle_wiring.py`

_`tw haggle` CLI verb wiring -- argparse only (dispatch itself needs a live daemon and is exercised at the protocol layer instead, see tests/test_protocol_haggle.py)._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_haggle_verb_is_wired_with_expected_defaults` | Haggle verb is wired with expected defaults. |
| `test_haggle_verb_accepts_overrides` | Haggle verb accepts overrides. |
