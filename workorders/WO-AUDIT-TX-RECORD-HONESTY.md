# WO-AUDIT-TX-RECORD-HONESTY — Session TX-record / transcript-log secrets honesty (F6)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **DONE (unpushed)** 2026-07-25 · tip **`c21cd1c`** (CC; push gated with F2/F6 lane gate)
> Type: harden · Phase: audit · Seat: impl-claudecode-aiclient
> Refs: `canon/engine/session-engine.md:146-153` · `connection.py` · `session.py` · `test_tx_record_honesty.py`

## Goal
Align the TX-record / transcript-log paths (`connection.py` + `session.py`) so they never embed raw credentials on the wire or in the ledger row.
Three sinks named in canon §146-153: transcript log · ledger row · `sent_input`. This WO covers the first two live sinks; `LedgerWriter` (`ledger.py`) is still CUT — the ledger sink constraint is forwarded to whichever WO ports the ledger.

## Scope
- `connection.py` — TX-record write path: credential scrub before log
- `session.py` — transcript-log path: credential scrub before append
- `tests/test_tx_record_honesty.py` — NEW: falsification test proving log/TX never contain raw secrets
- 806 insertions total

## Constraints
- Do NOT touch `daemon.py` (LedgerWriter still cut)
- Push gated: awaiting Lane B+C Accept before F2/F6 push window
- **Standing constraint on ledger WO:** when `LedgerWriter` is ported, give the ledger row the same failure-path treatment as `connection.py`/`session.py` — the third sink will reintroduce F6 unless explicitly told not to

## Accept
- `test_tx_record_honesty.py` passes: no raw credential in transcript log
- `test_tx_record_honesty.py` passes: no raw credential in TX-record output
- Suite green at `c21cd1c`

## Proof
```bash
git show --stat c21cd1c
pytest tests/test_tx_record_honesty.py -v
```

## Refs
CC STATUS @ 13:45:26Z · SHA `c21cd1c` (806 insertions) · `canon/engine/session-engine.md:146-153` · push gated on F2/F6 window
