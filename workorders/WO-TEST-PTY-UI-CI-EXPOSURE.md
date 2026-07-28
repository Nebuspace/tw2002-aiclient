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
