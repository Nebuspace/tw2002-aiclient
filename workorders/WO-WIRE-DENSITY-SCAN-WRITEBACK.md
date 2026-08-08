# WO-WIRE-DENSITY-SCAN-WRITEBACK

**Goal:** `density_scan.parse_density_scan`/`DENSITY_VALUE_TABLE` are built and
unit-tested against synthetic fixtures, but nothing in the live tick/protocol
path calls them, and there is no writer that turns a decoded density reading
(including the fighter-presence-via-absence inference canon names) into a
world_model sector field.

**Scope:**
- A live-screen classify call site for density-scan screens (mirror
  `game_data_capture.py`'s StarDock capture pattern)
- A `world_model` writeback path for the decoded density/presence value
- `tests/` covering both the call site and the writeback

**Constraints:**
- Fail-closed on ambiguous/unparseable readings — never write a guessed value
- Flag output as HYPOTHESIS/unverified until a real multi-sector density-scan
  screen capture exists (same two-layer discipline as game-data-store.md) —
  do not claim verified numbers from synthetic fixtures alone

**Accept:**
- Live classify path reaches parse_density_scan on a density-scan screen
- world_model gains a writeback field for the decoded value, tagged
  unverified/hypothesis pending real capture

**Refs:** canon/engine/world-model.md:250-254; 6-lens aiclient audit 2026-08-08T02:12Z
