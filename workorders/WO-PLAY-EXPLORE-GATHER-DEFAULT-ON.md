# WO-PLAY-EXPLORE-GATHER-DEFAULT-ON

**Status:** READY  
**Depends:** `main` ≥ `cdf3797` (#264)  
**Max GO:** 2026-07-30 — Explore should enter first-sight ports and ingest
commodity tables by default in Play.

## Goal

When Play Explore arrives at an unexplored / first-sight sector with a port
whose commodities are not yet stored, the run docks (`P` → trade report `T`)
and ingests commodities + quantities into the world model — without requiring
the operator to press `D` first.

## Current truth

- Dock+ingest path already exists: `sector_explore.port_needs_dock` +
  `_dock_and_ingest` (dialect known; refuse unrecognized menus; never send
  Attack).
- Play starts with `explore_dock_opt_in = False` (`app.py`), so plain `E`/`y`
  warps past ports.
- CLI / daemon library default `dock_new_ports=False` stays as the safe
  omit-means-OFF contract for non-Play callers.

## Scope

1. **Play default ON:** initialize `explore_dock_opt_in = True` for a new
   Play explore arm cycle so confirm shows `+dock` and `explore_start` is
   called with `dock_new_ports=True` unless the operator toggles `D` off.
2. **Chrome honesty:** update offer / confirm / gather-hint copy so default-ON
   is clear and `D` is described as the way to *pass ports* / disable gather
   (not "D to gather" as the only path to the feature).
3. **Keep existing safety:**
   - only first-sight / missing-commodities ports (`port_needs_dock`);
   - free flyby / already-on-screen ingest stays unconditional;
   - unrecognized port UI → typed halt, no Attack letter;
   - fight-tolls remains default OFF and opt-in via `F`.
4. **Do NOT flip** CLI `--dock-new-ports` default or daemon
   `ExploreReport.dock_new_ports` / protocol omit-default to ON. Play is the
   surface Max changed; library callers stay refuse-not-coerce / omit=OFF.
5. Pins: Play default ON → `+dock` + payload True; `D` toggles OFF →
   `no-dock…` + payload False; CLI/daemon default still False; existing
   dock+ingest regression pins stay green.

## Out of scope

- Auto-trade / buying / selling.
- Fight-tolls default ON.
- Genesis / planet_management coach.
- Shared `run/` daemon restart without DEPLOY-WINDOW (prefer exclusive
  `--run-dir` / offline pins).

## Constraints

- Lead-seat direct (no Task/subagents this session).
- Smallest Play-default change; reuse `_dock_and_ingest`.
- No prompt field. No send outside the existing dock cascade.
- Explicit paths only.

## Accept

1. Fresh Play Explore confirm (no `D` pressed) shows `+dock` and starts with
   `dock_new_ports=True`.
2. With dock ON, first-sight port without stored commodities is docked and
   commodities ingested (existing offline fixture / pin path).
3. Pressing `D` before confirm flips to dock OFF (`no-dock…`) and starts with
   `dock_new_ports=False` (operator can still pass ports).
4. CLI / daemon library defaults remain OFF (regression pins).
5. Focused + full offline suite green.
6. live-prove: offline dock/ingest pins preferred (`n/a` diversity) unless a
   live exclusive-run-dir prove is used; no fight-tolls arm.

## Proof

```bash
pytest -q tests/test_play_explore_flags.py tests/test_sector_explore.py
# plus any app/offer pins touched
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- Max 2026-07-30: enter ports on unexplored sectors to collect commodities
- `app.py` `explore_dock_opt_in` · `cockpit/explore_flags.py`
- `session/sector_explore.py` `port_needs_dock` / `_dock_and_ingest`
- WO-EXPLORE-GATHER-VISIBLE · WO-EXPLORE-DOCK-DEFAULT-OFF · WO-EXPLORE-DOCK-DIALECT
- Plan: Nebuspace `.samantha/plans/play-explore-gather-default-on-2026-07-30.md`
