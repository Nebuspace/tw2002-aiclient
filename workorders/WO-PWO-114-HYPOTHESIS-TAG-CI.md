# WO-PWO-114-HYPOTHESIS-TAG-CI — hypothesis-tag discipline CI gate

> Status: **DONE** · origin `e065ffa` (#347) · seat `impl-aiclient-cursor` · Accept 2026-08-03  
> Type: harden / CI · PWO-114  
> Tip base: `6824d5d` → merged `e065ffa`

## Goal
Make PWO-100's `assert_all_unverified_tagged` **run in CI**, with a deliberate-fail fixture proving the gate bites.

## Scope
- A: `scripts/hypothesis_tag_ci_guard.py` (real `port_economics`, not a mock)
- B: `scripts/test_hypothesis_tag_ci_guard.sh` (tip green + `--self-test-fail`)
- C: wire step into `.github/workflows/suite.yml`
- D: ULTRACODE + P9 PREP tip honesty → LIVE
- E: this WO file

## Constraints
- Inspect real `port_economics` module — coach_kb flags alone ≠ CI
- No Layer-B invent · no PWO-112 · no live arm

## Accept
1. CI suite step runs the guard on tip → green
2. `--self-test-fail` / shell harness proves untagged fixture exits non-zero
3. Guard imports `tw2002_aiclient.port_economics.assert_all_unverified_tagged`

## Proof
`./scripts/test_hypothesis_tag_ci_guard.sh` · CI suite · live-prove n/a (CI-infra / offline)
