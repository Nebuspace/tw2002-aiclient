# WO-STATUS-STAMP-SWEEP — Align workorder Status lines with git reality

**Status:** OPEN · EXECUTE · MED · Claude Code (`impl-claudecode-aiclient`)  
**Posted:** 2026-07-28T22:36Z · Max GO (stamp sweep)  
**Refs:** CC tip-check 22:15Z · `.samantha/plans/open-queue-stamp-lag-20260728.md`

## Goal

Flip stale **OPEN/READY/BANKED** Status lines to **DONE** (or honest residual) when an implementing commit already exists on `origin/main` and Accept is met. Do not invent product.

## Method (load-bearing)

1. Start from CC's ~20 stamp-lag candidates (or re-scan with `^WO-ID:` subject match — not bare `--grep`).
2. Per WO: read Accept → verify tip symbols/tests → Status DONE with ship PR/SHA **or** leave OPEN with one-line residual.
3. Near-miss names: `WO-TEST-TIMING-ASSERT-ORDER` ≠ `…-SCOPE` (#185).
4. `WO-EXPLORE-AUTOMATION-GATE` stays OPEN until #202 live is on main (or stamp live line closed if #202 already merged).

## Accept

1. ≥15 Status lines corrected with evidence (or fewer with explicit empty remainder).
2. No product code changes outside `workorders/**`.
3. Suite green · STATUS · live-prove `n/a`.

## Constraints

No force-close of Max-gated banks (`DISCOVERED-TO-TAUGHT`, `STATUS-EXPOSE` if still HELD on tip, combat until EXEC lands). Public-safe.
