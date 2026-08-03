# WO-PWO-111-RX-REDACTION — RX transcript redaction (password-anchor / post-secret)

> Status: **DONE** · seat `impl-aiclient-cursor` · hub GO 2026-08-03T15:22:00Z  
> Type: harden · PWO-111 residual (2) logging half  
> Tip base: `de44dfa` (#371)

## Goal
Extend TX redaction discipline onto RX **transcript logging** sinks only — same password-anchor / `secret=True` vocabulary; additive only.

## Scope
- A: `logging_util.should_redact_rx` + `TranscriptLogger` note
- B: `connection._log_rx` + `_redact_rx` echo window (operator TX arms/clears; TX-IAC ignored)
- C: tip-honesty PREP / ULTRACODE / doctrine Code Divergence #1 narrow
- D: tests (`test_connection` RX pins · login echoing-server transcript absence)

## Out of scope
- Live screen / `watch` paint (still may show echo)
- Attach heuristic residual (3)
- Parse / classify / settle / session-control changes
- New match vocabulary

## Accept
- Password-shaped RX chunk → `log_redacted`, never raw bytes in `session-*.log`
- After `secret=True` TX, echo without the word `password` still redacted until next non-secret operator TX
- Ordinary game RX still `log_raw`
- Doctrine / PREP residual (2) names live-paint, not transcript log

## Proof
`pytest tests/test_connection.py tests/test_logging_util.py tests/test_login_redaction.py -q`  
Live-prove: **n/a** (offline redaction sinks; no live TWGS / diversity arm)

## Hazards
Never un-redact. Never widen the password RE without a fresh GO.
