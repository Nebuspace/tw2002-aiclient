# WO-AUTOLOOP-CYCLE-PROGRESS — Play hint-band cycle progress chrome

**Status:** OPEN · EXECUTE · HIGH · visible automation · Cursor-only  
**Posted / seeded:** 2026-07-30T06:38Z · hub (after #243 cycles unlock)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `30c8e57` (`CYCLES_HARD_CEILING` + multi-pass `_run`)  
**Refs:** `canon/surfaces/mode-line-and-teach-controls.md` § hint band / AUTO-LOOP progress bar · `screens.py` `explore_band` · `#243` cycles

## Goal

While a taught AutoLoop run is live, claim the Play control-strip hint band
with canon's cycle-progress chrome:

`Playing <name> ▸ cycle/total [███░░]`

(ASCII `#` / `.` when unicode is off). Clear the band when the run stands
down. Teach tokens and explore offers already share this slot — never both.

## Scope

- Track **current pass** (1-based) on the live `RunReport` / `autoloop_status`
  wire (`cycle` or equivalent — name it; pin). Update as each `replay_loop`
  pass begins; total remains `report.cycles`.
- Pure composer (prefer `cockpit/`): given name + current + total +
  `unicode_ok`, emit the canon string. No invented counts.
- Play/`app.py`: while Autoloop is running, poll `autoloop_status` (existing
  adapter path) and set `explore_band` from the composer; clear on idle /
  finished / stand-down / explore-offer reclaim. Smallest wire — `#218`
  frozen.
- Focused tests: composer shapes · status exposes current/total · band
  updates / clears · one-pass still shows `1/1` (or honest equivalent) ·
  unicode/ASCII.

## Constraints

- Display-only — no change to halt/rails/`cycles` clamp/`force`/`param`.
- Do not invent progress when status is unknown (omit band / calm hints).
- No §A.2 / new deps / tooling. Lead-seat only.
- Live prove: `n/a` (offline chrome). Live multi-cycle arm still Max GO.

## Accept

1. Live multi-pass run advances `cycle/total` fill in the hint band.
2. Stand-down / finished clears the band (calm teach tokens return).
3. Composer + status pins green; suite green.
4. Live prove: `n/a`.

## Proof

```bash
pytest -q tests/test_autoloop_cycles.py tests/test_*cycle*progress*  # + new pins
pytest -q tests
```

STATUS names the status field(s) and the composer module path.

## Follow-on

- Max sacrificial GO: live `V`→`y` multi-cycle diversity with visible chrome.
