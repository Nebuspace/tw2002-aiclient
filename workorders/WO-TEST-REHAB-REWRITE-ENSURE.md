# WO-TEST-REHAB-REWRITE-ENSURE — Rewrite ensure / login tests off twclient

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`2d7d351`** (Cursor)
> Type: harden/rewrite · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-TEST-SUITE-REHAB.md` · `tests/test_ensure_*.py` · `tests/test_login_*.py`

## Goal
Rewrite ensure + login test files that import `twclient` onto greenfield `tw2002_aiclient`. Extend `FakeTWGS` / fake harness for mid-flow resume; proof tests (NEW/RETURNING branches, game_select recovery stubs); patch gaps only.

## Scope
- `tests/test_ensure_*.py` — ensure path tests (off twclient)
- `tests/test_login_*.py` (non-redaction) — login path tests (off twclient)
- FakeTWGS extension for mid-flow resume

## Outcome
Hub ACCEPT [WO-TEST-REHAB-REWRITE-ENSURE · SHIP · SHA 2d7d351].

## Refs
hub HANDOFF @ 03:57:18Z · hub ACCEPT @ 04:00:06Z SHA `2d7d351`
