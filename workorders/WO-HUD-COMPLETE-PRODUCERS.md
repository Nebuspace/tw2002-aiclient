# WO-HUD-COMPLETE-PRODUCERS

**Status:** BUILT · offline green · live partial (2 distinct hosts)  
**Depends:** `main` ≥ `102681e` · HUD bridge #226 · daemon lifecycle #252

## Goal

Populate all five HUD cells from truthful daemon-owned observations:
credits, sector, turns, empty cargo holds, and session profit.

## Scope

- Add a strict cargo-empty reader for the captured ship-info and port-report
  shapes.
- Extend `Session` with sticky cargo and session-profit snapshots.
- Add `hud_seed.seed_hud_after_join()`: at a safe `main_command` prompt only,
  issue one bounded `I` probe when credits / turns / cargo are unknown.
- Run the seed inside the existing `ensure` driver hold, both on already-there
  reuse and after successful login.
- Emit cargo and profit through the existing `status["hud"]` contract.

## Semantics

- **Cargo** = empty cargo holds (`cargo_holds_empty` in the historical HUD).
- **Profit** = current strict credits minus the first strict credits observed
  during this daemon session.
- The first strict credit observation establishes a known baseline and
  therefore a truthful profit of `0`.
- Unknown / damaged screens never overwrite sticky values.
- `I` is sent only when the current screen positively classifies
  `main_command`; fighter `Option?`, human-held, spectate, and other screens
  defer without sending.

## Accept

1. The live `ship_info_screen.txt` fixture yields credits `100000`, turns
   `25000`, cargo `60`, sector `15450`, and profit `0`.
2. A later strict credits reading updates profit by delta from the first
   reading and does not reset the baseline.
3. Cold join at `main_command` with unknown cells sends exactly one `I`;
   already-populated HUD sends none; failed/unconfirmed probes never raise.
4. `ensure` invokes the seed under its existing driver reservation on both
   success paths, after `mark_profile`.
5. Cargo/profit status cells carry daemon-computed finite ages and remain
   sticky across screens that omit them.
6. Focused tests and full offline suite pass.

## Proof

```bash
pytest -q tests/test_hud_complete_producers.py tests/test_hud_status_bridge.py
pytest -q -m "not live_login and not pty_ui"
```

Live prove uses an isolated run directory or the default daemon only after a
hub-mediated deploy window; no turn-spending arm is required.

## Result

- Focused: `79 passed`.
- Full offline: `6401 passed`.
- Live isolated-daemon success on two distinct catalog hosts, including one
  NEW registration and one subsequent RETURNING login. Both emitted all five
  non-null HUD cells after `hud_seed_reason=seeded`.
- Additional catalog hosts stopped in pre-existing login/spawn paths before
  HUD seeding (`unknown`, `fighter_encounter`, missing saved password, or
  spawn timeout). Therefore the repository's three-host merge diversity gate
  remains open; those failures do not contradict the two successful HUD
  observations and are not recorded as `n/a`.
