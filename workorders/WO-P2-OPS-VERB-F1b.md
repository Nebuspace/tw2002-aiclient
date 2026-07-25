# WO-P2-OPS-VERB-F1b — tw attach secret-keystroke redaction

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`582c210`** (Cursor)
> Type: harden · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-F-PREP.md` F1b · `canon/architecture/secrets-and-credentials.md`

## Goal
Port/rehab attach secret-keystroke redaction from archive `test_attach_redaction` onto greenfield tip so history/ledger never store raw secrets from `tw attach`. Redact-at-send; marker in history/transcript. Trace-Ledger attach sink banked for when ledger ports.

## Scope
- `tw2002_aiclient/session/` daemon/session attach path + redaction hooks
- `tests/test_attach_redaction.py` greenfield rewrite
- Un-ignore in `pytest.ini`

## Constraints
- No spectate F2; no chrome
- Do not invent ledger if absent (❓ if substrate missing)
- Secrets never echoed in history ring

## Accept
1. Redaction tests green + un-ignored in `pytest.ini`
2. STATUS cites what redacts where
3. Path-leak green

## Proof
6 redaction tests green + full suite exit 0. Hub Completeness 94 / Quality 94 / Safety 96 / Craft 93 → SHIP.

## Refs
`WO-P2-OPS-VERB-F-PREP.md` F1b · archive `test_attach_redaction` · hub Accept + Push GO @ 14:46:58Z
