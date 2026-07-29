# WO-EXPLORE-DOCK-DEFAULT-OFF — CLI/Play dock arm defaults OFF until dialect known

**Status:** OPEN · EXECUTE · CRITICAL · hub GO 2026-07-29 (live regression on main)
**Seat:** Cursor (`impl-aiclient-cursor`) · Live: n/a (default flip) or brief smoke
**Refs:** #205 MERGED `fdcbd1c` · Cursor live STATUS 00:14:23Z · CC FINDING 00:16:56Z

## Finding (live on main)

With `dock_new_ports` default **ON**, explore sends `P` at first-sight port; menu marker `"enter your choice"` (single fixture) fails on gone_rogue / academy / a_net → `dock_screen_unrecognized` → **whole run HALTs**. Map-fill terminates early; operator parked in unrecognized menu. Safety half correct (no blind `T`). Turns: 0 burned. Default-ON is the regression.

## Accept

1. CLI `--dock-new-ports` / `--no-dock-new-ports`: **default OFF** (library already False). Flip the pin that asserted default ON.
2. Play explore arm: stop passing `dock_new_ports=True` (omit or False). Opt-in only via explicit flag/path.
3. Pins updated both directions; suite green.
4. Do **not** loosen halt / skip-and-continue / widen marker in this WO.
5. STATUS when done. Live prove n/a for default flip (reason: offline contract change; residual dialect WO separate).

## Out of scope

Teaching new dock dialects; changing halt behavior; classify (#207).
