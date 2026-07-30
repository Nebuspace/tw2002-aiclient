# WO-WIRE-EXPLORE-DECISION-LINES — DECISIONS pane shows live explore next-hop

**Status:** OPEN · EXECUTE · HIGH · visible automation · unused-code WIRE · Cursor-only  
**Posted / seeded:** 2026-07-30T07:18Z · hub (IDLE-KICK feed; post-#244)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `763380b`  
**Refs:** `explore.format_explore_decision_lines` (test-only today) · `sector_explore.explore_run_wire` · Play DECISIONS · unused-code tip `format_explore_decision_lines`

## Goal

`format_explore_decision_lines` already composes canon DECISIONS-pane lines for
an explore tick — but **no product caller** reaches it. While a Play explore
run is live, the DECISIONS pane should show the active intent + next hop
(honest empty / "no frontier" when unknown), not only the calm coach/empty
state.

## Scope

1. **Wire field:** track the explorer's last planned next sector on
   `ExploreReport` (update when a warp target is chosen each tick); expose as
   `run.next_sector` on `explore_status` (`null` when unknown — never invent).
2. **Also expose** `run.dock_new_ports` if still missing from the wire (same
   honesty as `fight_tolls` / `intent`).
3. **Composer reuse:** product path calls
   `explore.format_explore_decision_lines` (map `map_fill`→`mapfill`,
   `find_stardock`→`stardock`; build the minimal plan-shaped object the
   composer already reads). Do **not** fork a second string table.
4. **Play surface:** while explore poll is active, feed those lines into the
   DECISIONS panel (preferred: overlay on the status dict the draw path
   already passes to `compose_decisions_lines` / fold — smallest seam;
   `#218` frozen). Clear when explore stands down. Do not steal the band from
   cycle-progress / explore_band chrome.
5. Focused pins: wire exposes next_sector · composer called from non-test ·
   DECISIONS updates/clears · unknown → honest omit/empty lines from composer.

## Constraints

- Display-only — no change to explore halt / dock default / fight_tolls.
- No §A.2 / new deps / tooling. Lead-seat only.
- Live prove: `n/a` (offline chrome). Live explore diversity still Max GO.

## Accept

1. Live explore (offline harness) → DECISIONS shows intent + next hop via
   `format_explore_decision_lines`.
2. `explore_status.run.next_sector` present (int or null).
3. Stand-down clears the explore overlay.
4. Suite green · live `n/a`.

## Proof

```bash
pytest -q tests/test_explore.py tests/test_*explore*decision*  # + new pins
pytest -q tests
```

STATUS names the wire field + Play overlay seam.

## Disposition

Closes unused-code tip-check **WIRE** for
`tw2002_aiclient.explore:format_explore_decision_lines`.

## Hub CI note

Suite re-fired after tip synchronize miss (2026-07-30T07:45Z).
