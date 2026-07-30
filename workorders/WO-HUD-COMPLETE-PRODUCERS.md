# WO-HUD-COMPLETE-PRODUCERS

**Status:** BUILT · offline green · live blocked once on unlimited-turn confirm · REVISE in flight  
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
- Seed completeness is **credits + empty cargo holds**. Turns are sticky when
  ship-info states them; unlimited-turn variants that omit `Turns left` leave
  the turns cell honestly absent and still count as `seeded`.
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
- Live isolated-daemon matrix on tip `c78e553`: 3 distinct hosts fully seeded
  (`academy_of_tradewars` RETURNING, `gone_rogue` RETURNING, `joes_tavern` NEW).
- Two additional NEW hosts reached `main_command` but unlimited-turn ship-info
  omitted `Turns left`, so the old Turns-based confirm returned
  `probe_unconfirmed` while credits/cargo were on screen. REVISE: confirm on
  `Credits :`, treat credits+cargo as seed-complete, turns may stay absent.
- Other catalog hosts stopped in pre-existing login paths (`unknown`,
  `fighter_encounter`, missing saved password). Those are `NOT-ATTEMPTED` /
  login-blocked cells, not `n/a`.
