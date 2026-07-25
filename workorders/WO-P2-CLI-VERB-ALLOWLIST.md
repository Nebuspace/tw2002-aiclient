# WO-P2-CLI-VERB-ALLOWLIST — Fix full-suite RED from OPS-VERB-A (allowlist screen/stop)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`7f9f1d4`** (Cursor)
> Type: harden/fix · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` allowlist note

## Goal
Fix full-suite RED since OPS-VERB-A: `tests/test_cli_log.py::test_parser_has_status_and_ensure_only` still asserted `{status, ensure}` only; live parser has `screen`/`stop`. Rename test + expand allowlist to match shipped verb set so future slice additions don't re-break.

## Scope
- `tests/test_cli_log.py` — rename test + update allowlist to shipped verb set
- No code changes; no new verbs

## Constraints
- Prefer subset-or-exact shipped set so slice B+ don't re-break
- Full `pytest tests/` green (or attributed)
- No new verbs invented

## Accept
1. `test_cli_log.py` test green
2. Full `pytest tests/` green (or attributed)
3. Test name reflects shipped set

## Proof
`pytest tests/test_cli_log.py` + full suite exit 0. Hub Completeness 98 / Quality 97 → SHIP.

## Refs
hub Accept + Push GO @ 12:49:52Z · URGENT fix for OPS-VERB-A landing
