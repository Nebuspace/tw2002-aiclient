# WO-PWO-111-REDACTION-HONESTY — Tip honesty: TX redaction LIVE / ledger → 094

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T03:04:42Z  
> Type: docs tip-honesty · PWO-111  
> Tip base: `1375eed`

## Goal
Close the dishonest PARTIAL on PWO-111: tip-prove TX send/log redaction is LIVE; keep ledger redaction on PWO-094 (LedgerWriter deferred).

## Verify-first (done)
- Sink: `Session.send`/`send_raw` → `TelnetConnection._log_tx` → `TranscriptLogger.log_redacted` (+ LOGS `append_redacted`).
- Suites green on tip: login / attach / status / ensure / secrets-store / transcript_tail.
- `daemon.py` explicitly defers LedgerWriter (pairs 094).
- RX prompt/screen verbatim = canon carve-out, not a missed TX sink.

## Scope
- A: ULTRACODE PWO-111 → **TX-LIVE** (+ Phase-9 PREP blurb)
- B: `WO-P9-110-115-doctrine-PREP.md` tip refresh
- C: this WO file

## Constraints
Docs-only. No LedgerWriter invention. Hold 092 / 113. Do not claim full “logs **and** ledger” Accept.

## Accept
Inventory + PREP match tip: TX LIVE; ledger deferred to 094; named residuals (RX, heuristic) documented.

## Proof
Docs commit; suite n/a; live-prove n/a (docs).
