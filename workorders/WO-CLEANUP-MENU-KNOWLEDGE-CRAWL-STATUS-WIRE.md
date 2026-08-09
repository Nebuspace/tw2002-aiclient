# WO-CLEANUP-MENU-KNOWLEDGE-CRAWL-STATUS-WIRE

**Status:** IN-FLIGHT (self-directed residual after HOLD clear 2026-08-09)
**Priority:** LOW
**Source:** queue-aiclient.md WO-CLEANUP-MENU-KNOWLEDGE-CRAWL-STATUS-RETIRE (re-scoped WIRE)

## Goal

`record_crawl_status` is live (crawler stamps `menu_map.last_crawl`), but
`get_crawl_status` had zero product readers (test-only). Wire the reader into
`tw menumap` so partial-map provenance is operator-visible.

## Accept

1. `menu_map_summary_from_store` attaches `last_crawl` via `get_crawl_status`.
2. `format_menu_map_report` prints a `last-crawl:` line when stamped; omits when None.
3. `tw menumap --json` includes `last_crawl` in the payload.
4. Pytest covers stamped + unstamped paths.

## Out of scope

RETIRE of `get_crawl_status`; inventing crawl UI elsewhere; Max-gated surfaces.
