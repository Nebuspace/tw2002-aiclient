# WO-WIRE-COVERAGE-LEDGER-COUNTS — Coverage meter ← ledger actor counts

> Status: **IN FLIGHT** · seat `impl-aiclient-cursor` · hub self-scope HANDOFF 2026-08-03T05:41:00Z  
> Type: wire · cockpit pin  
> Tip base: `7788a33` (PWO-094 LedgerWriter LIVE)

## Goal
Replace the always-`None` coverage-meter counts in `screens.py` with real `app`/`human` tallies from the trace ledger now that `LedgerWriter` exists.

## Premise verified
- `screens.py` comment (pre-change): "When the ledger lands, ONLY this call changes — two counts replace the two `None`s"
- Tip `7788a33` has `tw2002_aiclient/ledger.py` + `VALID_SENDERS` actors
- Canon: `canon/engine/coverage-metrics.md` — count rows by `actor`; honest `?` when unavailable

## Scope
- A: `ledger.live_actor_counts` (absent → `(None,None)`; empty → `(0,0)`; skip non-`app`/`human`)
- B: `screens.py` Play draw path passes those counts into `compose_coverage_meter`
- C: tip-honesty docstring in `cockpit/covermeter.py`
- D: `tests/test_coverage_ledger_counts.py` + this WO

## Constraints
- No inventing from `status` / `last_sender`
- No live send / money-path / daemon attach in this WO (daemon per-dispatch wire remains a named residual)
- Offline unit proof only

## Accept
1. Fixture ledger with 3 app + 1 human → meter string `COV 75% · App 3 · Hum 1`
2. Absent ledger → still `COV ?`
3. Product source pin: draw path calls `live_actor_counts` (not hardcoded `None`s)

## Proof
`pytest tests/test_coverage_ledger_counts.py` · CI suite · live-prove **n/a**
