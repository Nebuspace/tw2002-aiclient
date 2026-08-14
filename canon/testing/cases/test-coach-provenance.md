---
type: Reference
title: Test Cases — test_coach_provenance
description: Teaching-provenance product callers (session report, coach CLI, counts helper).
resource: repo://tw2002-aiclient/tests/test_coach_provenance.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-08-14T20:35:00Z
---

# Test Cases — `tests/test_coach_provenance.py`

_Teaching-provenance product callers (session report, coach CLI, counts helper)._

| Test | Blurb |
|------|-------|
| `test_format_teaching_provenance_line_empty_share_is_question` | Empty share formats as ai-share=? with total=0. |
| `test_session_report_includes_teaching_provenance` | Session report carries teaching_provenance counts and formats them. |
| `test_coach_provenance_cli_text_and_json` | `tw coach provenance` prints text and `--json` payload. |
| `test_teaching_provenance_counts_is_product_callable` | `teaching_provenance_counts` is callable from product (session_report path). |
