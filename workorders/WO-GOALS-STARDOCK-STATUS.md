# WO-GOALS-STARDOCK-STATUS — GOALS StarDock row from world-model landmarks

**Status:** DONE · origin `abaf47c` (#250) · paper-close 2026-07-31 (product on main; banner was stale OPEN)  
**Posted / seeded:** 2026-07-30T08:44Z · hub (Play-visible after #249; Max "just go")  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `40ba197` · landmarks writers already on main (`WO-WM-LANDMARKS-WRITE` #165 · `_attribute_landmark` / #169 memory)  
**Refs:** `cockpit/goals.py` StarDock row · `world_stats.WorldStats` · `tests/test_status_vocabulary_guard.py` · `explore.find_landmark_sectors` · `world_model.STARDOCK_LANDMARK`

## Goal

Play GOALS still paints StarDock as **unknown** even after explore has written
`landmarks` (Ports-line ingest + StarDock-screen attribution). The panel
already knows how to render `@sector` / `found` when `status` carries
`stardock_sectors` / `stardock_found` — those keys are starved consumers.
`WorldStats` already refreshes `known_sectors` off the draw path; extend that
same seam so a successful refresh can disclose known StarDock landmarks.

## Why now

- Visible automation bias (Max): operator can *see* that StarDock was found.
- Allowlist reasons claiming "landmarks never written" are **stale** — writers
  landed; only the GOALS producer is missing.
- Offline-proveable; no live turn-spend; not safety-list.

## Accept

1. **Producer:** on `WorldStats.refresh(world_id)` (same call sites as today —
   chains popup / explore terminal poll — **never** on the draw path), cache
   StarDock landmark sectors from the world model (reuse
   `explore.find_landmark_sectors` + `world_model.STARDOCK_LANDMARK`, or an
   equivalent single reader — do **not** invent a second landmark spelling
   table).
2. **`merge`:** when the cache has a successful refresh:
   - if ≥1 StarDock sector → set `stardock_sectors` (list of ints) and
     `stardock_found=True` (do not clobber caller-supplied non-`None` values —
     same rule as `known_sectors`).
   - if refresh succeeded and the list is empty → **omit** both keys (leave
     GOALS `?`). Do **not** emit `stardock_found=False` from an empty scan —
     that glyph means *confirmed not found* and wrongly gates Ship/Hold rows.
3. **Vocabulary:** delete `stardock_found` and `stardock_sectors` from
   `STARVED_STATUS_ALLOWLIST` in `tests/test_status_vocabulary_guard.py`; update
   the stale "landmarks never written" prose in `world_stats.py` module doc.
4. **Pins:** nonempty landmarks → merge supplies sectors + found; empty after
   refresh → keys absent; draw-path wrap still does no world-model I/O beyond
   reading the cache; suite green.
5. **Live:** `n/a` (offline status overlay; no TWGS required).

## Scope

- `tw2002_aiclient/world_stats.py` (+ thin tests)
- `tests/test_status_vocabulary_guard.py` allowlist
- optional: `tests/test_world_stats.py` if present / new focused pins
- **Docs stamp (same PR, tiny):** mark
  `workorders/WO-LANDMARK-ATTRIBUTE-LAST-KNOWN.md` **DONE** — product consumer
  `_attribute_landmark` is already on main (writer half of this story).

## Out of bounds

- Do **not** implement formations catalogue / `formations_count` (BANKED
  `WO-FORMATIONS-CATALOG-PORT`).
- Do **not** emit confirmed-negative StarDock.
- Do **not** read world model on `status_provider` draw.
- No daemon / protocol / DEPLOY-WINDOW.
- No live `V`→`y` arm.

## Proof

```bash
pytest -q tests/test_status_vocabulary_guard.py tests/test_cockpit_goals.py \
  tests/test_world_stats.py tests/test_landmark_attribute.py -n0
# + suite green on the PR tip
```
