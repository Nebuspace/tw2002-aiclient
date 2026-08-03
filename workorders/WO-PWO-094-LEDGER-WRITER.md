# WO-PWO-094-LEDGER-WRITER — LedgerWriter (closes 094 + 025 residual)

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T05:00:12Z  
> Type: harden / substrate · PWO-094 (+ PWO-025 residual)  
> Tip base: `528252a`

## Goal
Ship a reborn `LedgerWriter` that appends one actor-tagged row per dispatch (`actor∈{app,human}`), matching `trace-ledger` canon, with secret redaction (pairs PWO-111 — no reinvent).

## Scope
- A: `tw2002_aiclient/ledger.py` (new)
- B: `tests/test_ledger.py` (schema round-trip + actor tags + secret redaction + refuse `ai`)
- C: ULTRACODE + P7/P9 tip honesty (094 LIVE; 025 ledger residual closed)
- D: this WO file

## Constraints
- Actors only via `VALID_SENDERS` — never default/`ai`
- Secrets → `<redacted>` input + prompt (secret flag or password-shaped prompt)
- No live TWGS arm
- Daemon live-wire of every dispatch may remain a named residual if not in this slice — STATUS must say so

## Accept
1. Unit schema round-trip on JSONL
2. Sample append with real `app` / `human` actor tags
3. Secret credential never lands in the file

## Proof
`pytest tests/test_ledger.py` · CI suite · live-prove n/a (offline ledger substrate)
