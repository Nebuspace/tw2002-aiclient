# WO-GUARDIAN-KEEPALIVE-LEDGER — Guardian D10 keepalive → Trace-Ledger

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T05:57:30Z  
> Type: wire · substrate  
> Tip base: after #353 (`b1fa950`) · sibling tip-honesty #354 may land in parallel

## Goal
Append one actor-tagged Trace-Ledger row when SessionGuardian's D10 idle keepalive sends a blank Enter — that path calls `session.send` directly and never enters `protocol.dispatch` / `_record_ledger`.

## Scope
- A: `SessionGuardian(ledger=…)` + `_record_keepalive_ledger` after keepalive send (`actor="app"`)
- B: `daemon.py` constructs one `LedgerWriter()`, passes it to guardian and `server.ledger` (no double writer)
- C: tests — keepalive → `actor=app` row; ledger None still sends; daemon share pin; no-ai remains covered by existing ledger suite
- D: this WO

## Constraints
- Accounting only — no change to when/whether keepalive fires
- No new sender; never `actor="ai"`
- Ledger failure must never kill the guardian tick
- Cite keepalive send + ledger call file:line in STATUS

## Accept
1. Idle keepalive with injected ledger → one `actor=app` Trace-Ledger row
2. `ledger=None` → keepalive still sends, no crash
3. Daemon wires the same `LedgerWriter` to guardian and `server.ledger`

## Proof
`pytest tests/test_guardian.py tests/test_daemon_ledger_attach.py` · CI suite · live-prove **n/a** (offline harness; logging-only)

## Refs
- Hub GO 2026-08-03T05:57:30Z
- Prior: WO-DAEMON-LEDGER-WRITER-ATTACH / PR #353
- Canon: `canon/engine/trace-ledger.md`
