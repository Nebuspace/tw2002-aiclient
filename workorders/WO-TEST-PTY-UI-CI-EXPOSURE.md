# WO-TEST-PTY-UI-CI-EXPOSURE

**Goal:** Close the gap where **139** `pty_ui`-marked tests are permanently invisible to CI (`pytest -m "not live_login and not pty_ui"` in `.github/workflows/suite.yml`), so green suite never certifies that lane.

**Context:** Exclusion is *declared* (workflow comment → pending `WO-TUI-DEAD-TERMINAL-SPIN` / successor) — not a hidden deselect. Declared ≠ exercised. CC measured 5727 local vs 5588 under CI filter; CI log matches 5588. `live_login` currently matches **0** tests (inert clause).

**Standing Accept rule (ratified hub 2026-07-28):** any WO changing `pty_ui`-marked tests must quote a local `-m pty_ui` (or scoped path) RED-inject + GREEN-real proof in STATUS; CI suite alone is insufficient.

**Deliverable (pick coherent slice — do not silent-re-enable CI):**
1. Census appendix: count, owning files, why GHA excludes today.
2. Cadence proposal: scheduled hub/seat `pty_ui` lane **or** conditions to re-include in GHA when dead-terminal (or successor) is done.
3. Optional: thin smoke job / nightly — only with explicit Accept on cost/flake.

**Accept:** report + recommended next WO(s); live-prove `n/a` unless proposing a live lane.

**Refs:** CC 20:15:33Z · #192 F3 · suite.yml:77.

---

## Appendix — census + cadence (Cursor · #194 · tip measurement)

**Measured:** `2026-07-28` on tip after `#192` merge into this branch ·
`pytest --collect-only -m pty_ui -n0 -q` → **140** selected across **18** files
(WO text said **139** — that was pre-`#192`; teachband gained the left-shift falsify).

### Why GHA excludes today

| Layer | What |
|---|---|
| `.github/workflows/suite.yml:71–77` | `pytest -m "not live_login and not pty_ui"` — comment cites GHA run **30209603462**: `pty_curses_supported()` passed but cockpit `*_pty` stalled in `wait_frame` (30 failed / 37 errors), same hazard class as dead-terminal spin. |
| `pytest.ini` marker `pty_ui` | Documents exclusion until `WO-TUI-DEAD-TERMINAL-SPIN`. |
| `live_login` clause | Still in the marker expression; currently matches **0** tests (inert). |

**Stale coupling:** `WO-TUI-DEAD-TERMINAL-SPIN` is **DONE** (merged #2) and
`WO-DEAD-TERMINAL-SPIN-INTERMITTENT` is **DONE** (#184). Product busy-spin on a dead
pty is addressed; **GHA still excludes the whole `pty_ui` lane** because the
*wait_frame stall / runaway cost* hazard on runners was never separately
re-proven safe. Declared exclusion remains honest — it is just no longer gated
on an open product WO.

Green `suite` therefore **never certifies** these 140 tests. Standing Accept rule
(local `-m pty_ui` RED+GREEN for any WO that touches them) is the only load-bearing
gate today.

### Census by file (collect counts)

| N | File |
|---|---|
| 19 | `tests/test_cockpit_tones_pty.py` |
| 15 | `tests/test_cockpit_frame_pty.py` |
| 14 | `tests/test_cockpit_logsband_pty.py` |
| 12 | `tests/test_cockpit_hud_pty.py` |
| 10 | `tests/test_cockpit_viewport_pty.py` |
| 9 | `tests/test_cockpit_liveness_pty.py` |
| 8 | `tests/test_cockpit_fold_pty.py` |
| 8 | `tests/test_cockpit_viewport_paint_pty.py` |
| 7 | `tests/test_cockpit_decisions_pty.py` |
| 7 | `tests/test_cockpit_focus_pty.py` |
| 6 | `tests/test_cockpit_goals_pty.py` |
| 5 | `tests/test_cockpit_arm_pty.py` |
| 5 | `tests/test_cockpit_teachband_pty.py` |
| 4 | `tests/test_bank_unreadable_pty.py` |
| 3 | `tests/test_cockpit_conn_pty.py` |
| 3 | `tests/test_cockpit_covermeter_pty.py` |
| 3 | `tests/test_dead_terminal_spin.py` |
| 2 | `tests/test_cli_attach_unencodable_pty.py` |
| **140** | **total** |

Ownership: almost entirely cockpit Layer-B (`*_pty.py`) + bank/cli attach edge +
dead-terminal spin pins. Helpers: `tests/pty_helpers.py` (not marked; shared).

### Cadence proposal (do **not** silent-re-enable CI in this PR)

1. **Near-term (recommended): scheduled seat/hub `pty_ui` lane** — Cursor or CC
   idle turn, or hub cron: `pytest -m pty_ui -n0` (serial; xdist+curses is hostile)
   on `main`, post junit counts to coord. Cadence: ≥1× / weekday while GHA excludes.
   Cost: ~minutes local; flake surface is real (wait_frame) — treat RED as triage,
   not auto-merge block for unrelated PRs.
2. **GHA re-include conditions (successor WO, not this PR):**
   - Dedicated prove job (or one PR) runs `-m pty_ui` on GHA and finishes without
     `wait_frame` mass-stall / orphan CPU incident class.
   - Hard caps: job timeout + process-reap census (no PPID1 curses orphans).
   - Then flip `suite.yml` marker (and refresh `pytest.ini` marker prose) in the
     **same** PR that posts the green GHA log — never flip first.
3. **Optional thin smoke:** 1–3 representative files (`teachband_pty`, `liveness_pty`,
   `dead_terminal_spin`) as a separate workflow — only with explicit Accept on
   cost/flake; not proposed for merge in #194.

### Recommended next WO(s)

| ID (draft) | Goal |
|---|---|
| `WO-TEST-PTY-UI-SEAT-LANE` | Script + coord cadence for serial local `-m pty_ui` on `main`; STATUS template with collected/passed/failed; owner = idle Cursor or hub. |
| `WO-TEST-PTY-UI-GHA-REPROVE` | Run full `pty_ui` on GHA once under caps; if green, PR that removes `not pty_ui` from `suite.yml` + updates marker docs; if RED, bank wait_frame root-cause WO — **do not** re-enable. |
| (defer) nightly smoke subset | Only after seat lane proves stable for ≥1 week. |

**Out of scope / refused here:** changing `suite.yml` markers; adding a GHA job;
weakening the standing local-`pty_ui` Accept rule.

**live-prove:** `n/a` (docs/report; no login/session surface).
