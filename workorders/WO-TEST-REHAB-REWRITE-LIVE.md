# WO-TEST-REHAB-REWRITE-LIVE — Greenfield-rewrite the live test harnesses (off twclient)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`7b70279`** (Cursor)
> Type: harden/rewrite · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-TEST-SUITE-REHAB.md` · `tests/` harness files · `WO-TEST-REHAB-DELETE.md`

## Goal
Greenfield-rewrite the live pty / Layer-B proof harnesses that still import `twclient` (`test_spectate_app.py`, `test_spectate_layout.py`, `test_interactive_app.py`, `test_aiclient_play_panels.py` or equivalents). Port onto `tw2002_aiclient` — no `import twclient`; full suite green.

## Scope
- `tests/` pty/Layer-B harnesses — greenfield rewrite off `twclient`
- `tests/pty_helpers.py` · `tests/fake_client.py` (if not already ported in WO-P3-HARNESS-REHAB)

## Outcome
Hub ACCEPT [WO-TEST-REHAB-REWRITE-LIVE · SHIP · SHA 7b70279].

## Refs
hub HANDOFF @ 03:52:56Z · hub ACCEPT @ 03:56:42Z SHA `7b70279`
