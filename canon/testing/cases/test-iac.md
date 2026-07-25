---
type: Reference
title: Test Cases — Iac
description: IAC stripping + negotiation tests — no network involved.
resource: repo://tw2002-aiclient/tests/test_iac.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:07:30Z
---

# Test Cases — `tests/test_iac.py`

_IAC stripping + negotiation tests — no network involved._

| Test | Blurb |
|------|-------|
| `test_plain_data_passes_through` | Plain data passes through. |
| `test_escaped_iac_iac_is_literal_0xff` | Escaped iac iac is literal 0xff. |
| `test_do_ttype_replies_will_ttype` | Do ttype replies will ttype. |
| `test_ttype_subnegotiation_send_replies_with_terminal_type` | Ttype subnegotiation send replies with terminal type. |
| `test_do_naws_replies_will_and_sends_dimensions` | Do naws replies will and sends dimensions. |
| `test_unsupported_do_option_gets_wont` | Unsupported do option gets wont. |
| `test_do_echo_refused_server_should_echo` | Do echo refused server should echo. |
| `test_will_echo_accepted` | Will echo accepted. |
| `test_will_sga_accepted_data_interleaved` | Will sga accepted data interleaved. |
| `test_iac_split_across_two_feed_calls` | The state machine must survive an IAC sequence split at a recv() boundary. |
| `test_subnegotiation_split_across_feed_calls` | Subnegotiation split across feed calls. |
| `test_dont_replies_wont_and_wont_replies_dont` | Dont replies wont and wont replies dont. |
