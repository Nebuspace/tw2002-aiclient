# WO-PLAY-OFFER-LIVE-REPROVE

**Status:** OPEN  
**Posted:** 2026-07-27T05:02:00Z · follow-on after `WO-PLAY-OFFER-VISIBLE-ON-LIVE` (#79 → `0911d4b`)  
**Seat:** `impl-claudecode-aiclient` (live TWGS / Fable)  
**Depends:** main tip ≥ `0911d4b`  
**Plan:** `.samantha/plans/one-client-play-ladder-20260727.md`  
**Supersedes Accept of:** `WO-PLAY-LADDER-LIVE-PROVE` #76 (offer-invisible FAIL)

## Goal

Re-prove the one-client Play ladder on a **live TWGS** now that the offer paints on the mid control-strip when `log_tail` is populated: NEW char → `main_command` → **visible** offer → **E** → **y** → explore progress on hint band.

## Scope

- Live ensure/register + Play path only (no product code changes unless a new defect blocks Accept — then `❓ DECISION-NEEDED` + park).
- Fresh isolated config/run dirs under `/tmp/play-ladder-reprove-*` (same rules as `WO-PLAY-LADDER-LIVE-PROVE`: random catalog server, NEW char, `allow_register=true`).
- Audit under `audit/live-play-ladder-reprove-<shortsha>-<UTC>.md`.

## Constraints

- Do **not** change mid-strip / `explore_band` layout without hub GO.
- Do **not** press **E** blind if the offer is still invisible — FAIL honestly with frame evidence.
- Orphan daemons: document; do not mass-reap ppid=1 without hub ACK.
- CERT-JUNIT stays parked.

## Accept

1. NEW sacrificial character reaches `main_command` on a random catalog TWGS.
2. With populated `log_tail`, the mid-strip (or equivalent painted surface) shows an offer containing `press E` / explore-available wording — **observed**, not inferred.
3. **E** then **y** arms explore; hint band shows live progress (`explore N/5…` or `explore_band` equivalent).
4. Audit + STATUS with tip SHA, server key/host, game letter, and before/after frame notes (or screenshots/pty capture).

## Proof

Live session transcript / frame dump in the audit file. Unit suite alone is **not** Accept.

## Refs

- Tip `0911d4b` · PR #79 · DECISION `OPEN-PLAY-STATUS-MIDSTRIP` (`dcb5629`)
- Prior FAIL audit `audit/live-play-ladder-newchar-9795263-20260727T0430Z.md`
- Invariant: *offer → mid-strip · run progress → hint band*
