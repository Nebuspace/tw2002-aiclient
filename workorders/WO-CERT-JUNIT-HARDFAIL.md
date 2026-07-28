# WO-CERT-JUNIT-HARDFAIL — Seat cert: missing/empty junitxml = hard fail

**Status:** IN PROGRESS · EXECUTE · MED · Cursor-class · impl-aiclient-cursor  

**Posted:** 2026-07-26  
**Seeded for execute:** 2026-07-28T01:25Z · hub  
**Seat:** impl-aiclient-cursor  

## Goal

A seat that runs `pytest --junitxml=<path>` and finds no output file (or an empty / zero-test
file) at `<path>` must **hard-fail**, not silently report green.  Today a misconfigured or
zero-collecting run exits 0, the hub sees `PASS`, and the gate is bypassed without any tests
having run.

## Scope

- `scripts/` — cert scripts that invoke pytest with `--junitxml` (add the guard there), **or**
- A documented runbook section in the existing seat runbook at the path currently used for cert
  instructions (verify and cite the path in STATUS)

Tip-check first: prefer extending an existing cert / wire-sweep helper (e.g. junitxml parse in
`scripts/wire-sweep.py`) rather than inventing a parallel path.

## Constraints

- Do not change test collection logic or pytest configuration
- Guard fires on: file missing · file empty · `<testsuites tests="0"/>` · any parse error
- Guard must not fire if `pytest` itself exits non-zero (already a hard fail by other means)
- No new Python dependencies
- Do not touch `wo/CHAIN-DETECT-WIRE` / #128

## Accept

1. If `--junitxml` output is missing or empty after a zero-exit pytest run, the cert script
   (or runbook) exits non-zero with an explicit error message.
2. A normal passing run (≥1 test collected, file present) is unaffected.
3. `bash -n <script>` exits 0.  Include a shell or Python unit-test pin if practical.

## Proof

Demonstrate: `pytest --collect-only -q --junitxml=/tmp/junit_test.xml tests/test_nonexistent.py`
exits 0 but the guard detects empty/missing xml and returns non-zero.
Report the guard path in STATUS.
live-prove **n/a** (CI/cert tooling).
