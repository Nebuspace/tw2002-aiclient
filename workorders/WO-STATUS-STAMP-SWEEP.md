# WO-STATUS-STAMP-SWEEP — Align workorder Status lines with git reality

**Status:** OPEN · EXECUTE · MED · seat `impl-aiclient-cursor`  
**Posted:** 2026-07-28T22:36Z · Max GO (stamp sweep)  
**Re-armed:** 2026-08-02T04:08Z · hub refill after #317  
**Branch:** `wo/STATUS-STAMP-SWEEP`  
**Depends:** `main` ≥ `20b4646` (#317 FORMATIONS)  
**Refs:** CC tip-check 22:15Z · `.samantha/plans/open-queue-stamp-lag-20260728.md` · #318 banner stamp (partial)

## Goal

Flip stale **OPEN/READY/BANKED** Status lines to **DONE** (or honest residual) when an implementing commit already exists on `origin/main` and Accept is met. Do not invent product.

## Method (load-bearing)

1. Re-scan `workorders/*.md` for stale OPEN/READY/BANKED banners; verify each with `git log` / `gh pr` / tip symbols — not bare `--grep`.
2. Per WO: read Accept → verify tip → Status DONE with ship PR/SHA **or** leave OPEN with one-line residual.
3. Near-miss names: `WO-TEST-TIMING-ASSERT-ORDER` ≠ `…-SCOPE` (#185).
4. **Must include** stamping `WO-FORMATIONS-CATALOG-PORT` (#317 `20b4646`) and closing residual READY on `WO-BANNER-STAMP-SWEEP-317` / `WO-FOLD-EMPTY-DECISIONS-DOC` if still lying.
5. Do **not** force-close Max-gated banks (`DISCOVERED-TO-TAUGHT`, `CANON-LCHAINS-DISCOVERED-SECTION`, `GITHUB-APP-LIVEPROVE`, etc.).

## Accept

1. ≥15 Status lines corrected with evidence (or fewer with explicit empty remainder + table of what remains and why).
2. No product code changes outside `workorders/**` (and this WO).
3. Suite green (or n/a if docs-only and CI suite still runs green on PR) · STATUS · live-prove **n/a**.

## Constraints

Docs/status honesty only. Public-safe. Explicit paths — never `git add -A`.
