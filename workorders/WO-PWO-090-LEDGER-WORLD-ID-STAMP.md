# WO-PWO-090-LEDGER-WORLD-ID-STAMP — Trace ledger world_id row stamp (Option A)

**Status:** build
**Hub GO:** 2026-08-03T13:29:00Z (Option A; Option B held)
**Branch:** wo/PWO-090-LEDGER-WORLD-ID-STAMP

## Goal
Stamp optional world_id on new Trace-Ledger rows; filter API on read_entries. No path migrate; never rewrite existing rows.

## Scope
- tw2002_aiclient/ledger.py — record_do world_id + read_entries filter
- session/protocol.py — resolve world_id from marked profile for do/send/attach
- DECISION-LEDGER-WORLD-ID-STAMP · world-identity tip
- tests/test_ledger.py

## Accept
1. New rows with world_id stamp when provided
2. Filtered read matches stamp; unstamped rows excluded from filter, untouched on disk
3. Omit field when unknown; no Option B path
4. Offline tests; live-prove n/a

## Proof
pytest tests/test_ledger.py tests/test_daemon_ledger_attach.py -q
