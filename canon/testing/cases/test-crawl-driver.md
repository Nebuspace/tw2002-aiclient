---
type: Reference
title: Test Cases — test_crawl_driver
description: Live-crawl driver tests — canon K3's two structural legs.
resource: repo://tw2002-aiclient/tests/test_crawl_driver.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_crawl_driver.py`

_Live-crawl driver tests — canon K3's two structural legs._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_leg1_refusal_happens_with_the_session_factory_spy_at_exactly_zero` | Canon: the refusal happens "before opening a single connection or invoking the session factory even once". |
| `test_leg1_refusal_leaves_no_file_the_driver_would_have_created` | The other half of "before opening a single connection": a refusal produces no log file and no knowledge store — zero side effects. |
| `test_leg1_refusal_never_consults_the_caller_supplied_stop_hooks` | The gate is checked before abort_check / is_driver_fenced are ever consulted — a non-sacrificial profile refuses without touching any caller-supplied hook. |
| `test_leg1_profile_that_has_never_heard_of_the_flag_refuses` | Fail-closed by omission. |
| `test_leg1_only_an_explicit_true_opens_the_gate` | Fail-closed against a merely-truthy stand-in. |
| `test_leg1_unevaluable_truthiness_refuses_rather_than_raising_through` | Leg1 unevaluable truthiness refuses rather than raising through. |
| `test_leg1_refusal_survives_a_profile_with_no_name_attribute` | Leg1 refusal survives a profile with no name attribute. |
| `test_leg1_gate_opens_for_a_genuinely_sacrificial_profile` | Non-vacuity for the whole Leg 1 block: the gate is not simply refusing everything unconditionally — an explicit True does crawl. |
| `test_leg2_abort_lands_between_sends_never_mid_send` | The load-bearing Leg 2 proof. |
| `test_leg2_the_mid_send_detector_actually_detects_a_mid_send_stop` | Falsification of the detector above, not of the driver. |
| `test_leg2_stop_signal_is_checked_ahead_of_the_real_session_factory` | Canon: "the driver adds the abort check *ahead* of the real session factory". |
| `test_leg2_abort_on_the_very_first_boundary_stops_before_any_send` | The earliest possible stop: fired on the crawl's own root open, so nothing is ever sent and only the connect phase was logged. |
| `test_leg2_abort_reports_a_clean_stop_not_an_error` | An abort is the expected clean-stop path: it returns a result, never raises CrawlAborted out of the driver. |
| `test_leg2_driver_fence_is_an_independent_trigger_landing_the_same_way` | A human `tw attach` fencing the driver mid-crawl stops it at the next boundary via the identical clean path, with abort_check never tripping at all. |
| `test_leg2_abort_check_and_fence_report_distinguishable_reasons` | Leg2 abort check and fence report distinguishable reasons. |
| `test_leg2_crawl_aborted_never_escapes_the_driver` | CrawlAborted is an internal signal; a caller never has to catch it. |
| `test_completed_crawl_stamps_the_map_complete` | Completed crawl stamps the map complete. |
| `test_aborted_crawl_leaves_a_map_that_says_it_is_partial` | A half-completed crawl persists whatever it discovered. |
| `test_truncated_crawl_is_stamped_truncated_not_complete` | The max_nodes rail stopping a walk with frontier still queued is the other way a map ends up partial. |
| `test_a_refused_crawl_never_stamps_anything` | The refusal path writes nothing at all, so it cannot leave a stamp claiming a crawl happened. |
| `test_a_structural_failure_is_stamped_error_and_re_raised` | A genuine failure is observed and stamped, then re-raised — never swallowed into a result that looks like a finished crawl. |
| `test_log_is_well_formed_jsonl_with_the_expected_phase_sequence` | Log is well formed jsonl with the expected phase sequence. |
| `test_log_appends_across_repeated_runs_never_truncates` | Log appends across repeated runs never truncates. |
| `test_the_driver_never_logs_a_password_shaped_field` | The log is an operator-tailed artifact; nothing about a crawl needs a credential in it. |
| `test_driver_run_never_emits_a_state_changing_category` | Driver run never emits a state changing category. |
