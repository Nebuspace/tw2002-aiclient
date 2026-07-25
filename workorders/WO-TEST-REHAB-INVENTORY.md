# WO-TEST-REHAB-INVENTORY — Audit existing test suite: catalog live vs banked vs stale

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`7e75677`** (Cursor)
> Type: audit/docs · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `tests/` · `pytest.ini` ignore list · `WO-TEST-SUITE-REHAB.md`

## Goal
Catalog the test suite: which tests are live (collected + run), banked (`--ignore`d), or stale (import `twclient` / dead archive references). Produce inventory that gates WO-TEST-REHAB-DELETE and REWRITE.

## Scope
- `tests/**/*.py` — catalogue each file: live / banked / stale
- `pytest.ini` ignore list cross-check
- Output: inventory doc (or STATUS with table)

## Outcome
Hub ACCEPT [WO-TEST-REHAB-INVENTORY · SHIP · SHA 7e75677].

## Refs
hub HANDOFF @ 03:48:27Z · hub ACCEPT @ 03:51:26Z SHA `7e75677`
