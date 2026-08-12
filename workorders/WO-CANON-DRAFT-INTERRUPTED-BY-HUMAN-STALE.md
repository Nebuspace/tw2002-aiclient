# WO-CANON-DRAFT-INTERRUPTED-BY-HUMAN-STALE — correct "not yet consumed" note

**Status:** DONE · tip trace-ledger.md documents session_report consumer
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Fix `canon/engine/trace-ledger.md` claim that `interrupted_by_human` is
written but not consumed — tip `session_report.py` skips those rows by
default; `tw report --include-interrupted` exposes them.

## Accept

1. Divergence note names the live report consumer.
2. live-prove `n/a` (docs-only).

## Refs

- `session_report.py:104,151` · `session/cli.py:1758-1760`
