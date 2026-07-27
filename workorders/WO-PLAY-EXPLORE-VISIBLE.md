# WO-PLAY-EXPLORE-VISIBLE

**Status:** OPEN · **depends on** `WO-PLAY-EXPLORE-ADAPTER` on `main`; best after or with `WO-PLAY-EXPLORE-ARM`  
**Posted:** 2026-07-27T03:10:33Z · One-client Play ladder **L4**  
**Seat:** impl-aiclient-cursor (status poll) · CC may take if Cursor is mid-L1/L2  
**Plan:** `.samantha/plans/one-client-play-ladder-20260727.md`

## Goal

While explore runs (and when it finishes), Max **sees** progress in Play — `distinct_sectors` / `outcome` — without `tw explore status`.

## Scope (owned)

- `tw2002_aiclient/app.py` (and/or `screens.py` status_line refresh path): while an explore run is active (track a simple local flag set on successful arm start), poll `adapters.explore_status` on the existing redraw/status tick and set `status_line` like `explore 3/5…` → `explore completed (5)` / `explore halted: <reason>`
- Prefer status_line first. Optional: map explore halt into stopbanner **only** if an existing halt reason seam fits without inventing Autopilot STOP semantics — do not force-fit
- Tests with mocked `explore_status` snapshots

## Out of scope

- New CLI
- Protocol / ExploreRunner changes
- Full GOALS panel redesign

## Accept

1. During a mocked in-progress explore (`outcome` null/running, `distinct_sectors` increasing), status_line updates at least once with sector count
2. Terminal outcomes (`completed` / `halted` / `crashed`) produce a stable final status_line (not stuck on “Ensuring…”)
3. When explore is not active, no spurious explore status spam
4. Targeted pytest green

## Proof

Unit/pty with mocks. Live secondary: Play → confirm → watch status_line climb to ≥5 on micro.

## Refs

- `session/sector_explore.py` `explore_run_wire` fields
- `adapters.explore_status` (L2)
- `workorders/WO-PLAY-EXPLORE-ARM.md`
