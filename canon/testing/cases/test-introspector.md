---
type: Reference
title: Test Cases — test_introspector
description: TW-27 game-data introspector tests.
resource: repo://tw2002-aiclient/tests/test_introspector.py
tags: [testing, catalog, pytest, inventory]
timestamp: 2026-07-25T14:10:13Z
---

# Test Cases — `tests/test_introspector.py`

_TW-27 game-data introspector tests._

> **BANKED** — excluded from the default pytest run via `pytest.ini --ignore`. Catalogued for completeness.

| Test | Blurb |
|------|-------|
| `test_parse_shipyard_listing_clean_multi_ship_fixture` | Parse shipyard listing clean multi ship fixture. |
| `test_parse_shipyard_listing_skips_malformed_row_without_crashing` | Parse shipyard listing skips malformed row without crashing. |
| `test_parse_shipyard_listing_no_listing_on_screen_returns_empty_list` | Parse shipyard listing no listing on screen returns empty list. |
| `test_parse_shipyard_listing_anchors_to_latest_not_stale_scrollback` | Parse shipyard listing anchors to latest not stale scrollback. |
| `test_parse_shipyard_row_conforms_to_ship_row_schema` | Prove the parser's own output, plus a caller-supplied `last_verified_ts` (the persist layer's job -- see module docstring), fully satisfies `validate_ship_row`. |
| `test_parse_shipyard_listing_rows_load_via_game_data_loader` | End-to-end: introspector output, stamped with a timestamp the way the persist layer would, round-trips cleanly through `game_data.load_game_data`. |
| `test_non_introspected_source_is_rejected_by_validator` | Non introspected source is rejected by validator. |
| `test_parse_cargo_hold_price_clean_fixture` | Parse cargo hold price clean fixture. |
| `test_parse_cargo_hold_price_at_max_holds_returns_none` | The block is present and closed, but there's no price line to show (ship already at max holds) -- absence, never a guess. |
| `test_parse_cargo_hold_price_no_block_on_screen_returns_none` | Parse cargo hold price no block on screen returns none. |
| `test_parse_cargo_hold_price_anchors_to_latest_not_stale_scrollback` | Parse cargo hold price anchors to latest not stale scrollback. |
| `test_parse_cargo_hold_price_row_conforms_to_cargo_hold_row_schema` | Parse cargo hold price row conforms to cargo hold row schema. |
| `test_parse_cargo_hold_price_rows_load_via_game_data_loader` | Parse cargo hold price rows load via game data loader. |
| `test_cargo_hold_non_introspected_source_is_rejected_by_validator` | Cargo hold non introspected source is rejected by validator. |
| `test_parse_scanner_listing` | Parse scanner listing. |
| `test_parse_scanner_listing_no_listing_on_screen_returns_empty_list` | Parse scanner listing no listing on screen returns empty list. |
| `test_parse_transwarp_listing` | Parse transwarp listing. |
| `test_parse_item_listing` | Parse item listing. |
| `test_parse_item_listing_skips_malformed_row_without_crashing` | Parse item listing skips malformed row without crashing. |
