# WO-DAEMON-LEDGER-WRITER-ATTACH — Daemon send choke → LedgerWriter

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T05:46:20Z  
> Type: wire · substrate  
> Tip base: `2107718` (coverage←ledger LIVE; LedgerWriter module LIVE)

## Goal
Append actor-tagged Trace-Ledger rows at the daemon send choke so live do/send/attach populate `state/ledger.jsonl` (coverage meter + miner stop seeing empty/absent ledgers).

## Scope
- A: `protocol._record_ledger` + `record_attach_keystroke` (actor∈{app,human}; secret redaction; no ai)
- B: `protocol` verbs `do` / `send` call `_record_ledger` after wire send
- C: `daemon._handle_attach` calls `record_attach_keystroke` after `send_raw`; `server.ledger = LedgerWriter()`
- D: tests + this WO; tip honesty on attach-redaction docstring

## Constraints
- Accounting only — no new send path / no new senders / no AI
- Ledger failure must never fail the verb
- Cite actual choke file:line in STATUS

## Accept
1. `dispatch(..., "send", ...)` with server.ledger → one `actor=app` row
2. Attach helper → `actor=human`; secret → `<redacted>`
3. Source pin: daemon no longer claims ledger deferred

## Proof
`pytest tests/test_daemon_ledger_attach.py` · CI suite · live-prove **n/a** (offline daemon harness)

## Refs
- Hub GO 2026-08-03T05:46:20Z
- Canon: `canon/engine/trace-ledger.md` · PWO-094 / PWO-025 residual
