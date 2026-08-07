# WO-FIX-EXPLORE-SKIP-SPECIAL-PORTS

**Parent:** `WO-ESCALATE-LIVE-DRIVE-DOUBLE-MONEY-FINDINGS` (hub live-drive 2026-08-06).

**Goal:** Explore with `dock_new_ports` must skip Class 0 Special (StarDock)
ports instead of docking and halting the run with `dock_report_unreadable`.

**Scope:**
- `tw2002_aiclient/session/sector_explore.py` — `port_needs_dock`
- `tests/test_explore_dock_new_port.py` — falsification pin
- this WO file

**Out of scope:** trade-chain CLI (shipped #509); live witness re-drive
(`WO-LIVE-WITNESS-FIRST-TRADE-LOOP`); classifier rewrite; inventing a
`"Special"` class into the world model.

**Constraints:**
- Class 0 Special flyby is already *present but classless* (`port == {}`) per
  `read_port_from_sector_status` — do not invent a class string.
- Skip only when no commodity class triple is present; real `([BS]{3})` ports
  still dock on first sight.
- Hub GO: HANDOFF 2026-08-07T02:32Z / redirect after #509 merge.

**Accept:**
1. `port_needs_dock(PortRead(observed=True, port={}), None)` is False.
2. Existing dock pins stay green (Ports:None / unobserved / first-sight BBS /
   stored commodities).
3. live-prove: `n/a` (offline skip predicate; residual live half is
   WO-LIVE-WITNESS-FIRST-TRADE-LOOP).

**Proof:** `pytest -q -n0 tests/test_explore_dock_new_port.py`
