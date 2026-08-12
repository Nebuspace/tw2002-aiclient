# WO-BUILD-COVERAGE-METRICS-TEACHING-PROVENANCE-WIRE

**Status:** IN FLIGHT (impl-aiclient-h1 · hub audit-refill HANDOFF 2026-08-12T05:05:10Z)

## Goal

Wire the already-built teaching-provenance coverage kernel
(`teaching_provenance_counts` / `teaching_provenance_share`) into operator-visible
surfaces. Kernel-only DONE (`WO-BUILD-COVERAGE-METRICS-TEACHING-PROVENANCE-AXIS`) left
zero production callers.

## Scope

- `tw2002_aiclient/coverage_metrics.py` — `format_teaching_provenance_line`
- `tw2002_aiclient/session_report.py` — fold provenance into `tw report` / stop digest
- `tw2002_aiclient/coach_cli.py` — `tw coach provenance` (read-only rule-store axis)
- `canon/engine/coverage-metrics.md` — note wired surfaces
- tests + this WO

## Out of scope

- Changing live covermeter app/human share
- FOCUS gutter width (CLI surfaces only)
- Consolidating credentials `save_password` (separate READY row)

## Accept

1. At least one product (non-test) caller of `teaching_provenance_counts`
2. `tw report` / `format_session_report` prints a teaching-provenance line when the
   rule store is readable (best-effort; never fails the report)
3. `tw coach provenance` prints the same axis (text + `--json`)
4. Unit tests cover both surfaces

## Proof

- `.venv/bin/python -m pytest tests/test_coverage_teaching_provenance.py tests/test_session_report.py tests/test_coach_provenance.py -n0 -q`
- live-prove: **n/a** (offline CLI + pure read of rule store / ledger)

## Refs

- Hub HANDOFF 2026-08-12T05:05:10Z
- `canon/engine/coverage-metrics.md` § Teaching-provenance axis
- Prior kernel: `WO-BUILD-COVERAGE-METRICS-TEACHING-PROVENANCE-AXIS`
