# WO-TIP-HONESTY-RECORDER-ATTACH-LEDGER — Recorder docstring after #353/#355

> Status: **DONE** · origin `8f3a746` (#356) · seat `impl-aiclient-cursor` · Accept 2026-08-03  
> Type: docs / tip honesty

## Goal
Stop `loops/recorder.py` (and the related `loops/store.py` listing note) from citing the pre-#353 "attach ledger deferred / no ledger" premise now that Trace-Ledger attach + keepalive are LIVE.

## Scope
- A: `loops/recorder.py` module docstring — acknowledge attach ledger LIVE; recorder still does not consume it
- B: `loops/store.py` — Trace-Ledger exists; listing still does not invent `demo_profit`
- C: stamp `WO-GUARDIAN-KEEPALIVE-LEDGER` DONE

## Accept
Docs match tip; no behavior change.

## Proof
Diff-only · live-prove **n/a** (docs)
