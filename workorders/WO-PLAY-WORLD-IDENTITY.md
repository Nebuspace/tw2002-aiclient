# WO-PLAY-WORLD-IDENTITY

**Status:** DONE · tip `5e20ce2` · #70  
**Posted:** 2026-07-27T03:10:33Z · One-client Play ladder **L1**  
**Seat:** impl-aiclient-cursor (volume · restore + tests)  
**Plan:** `.samantha/plans/one-client-play-ladder-20260727.md`

## Goal

Restore a live `world_id(host, game_letter, handle)` helper under `tw2002_aiclient` so Play can key explore / world-model without inventing a CLI `--world-id` for every session.

## Why

Explore protocol **requires** `world_id`. CLI forces the operator to pass it. One-client path cannot. Canon: `canon/engine/world-identity.md`. Pre-rebirth seed (byte-contract): `archive/pre-rebirth-2026-07-23/code/twclient/world_identity.py`. Existing `tests/test_world_identity.py` still imports dead `twclient.world_identity` — fix the import to the restored module.

## Scope (owned)

- `tw2002_aiclient/world_identity.py` (**new** — port from archive seed; package path `tw2002_aiclient`, not `twclient`)
- `tests/test_world_identity.py` — import path fix only (+ keep behavior pins)
- Optional one-line package re-export if the tree already has a pattern for it — do not invent a second API

## Out of scope

- Play / adapters / explore wire (L2+)
- Canon prose push
- Renaming on-disk `state/world/*` slugs from older hub runs
- Stealing teach `T` key

## Accept

1. `from tw2002_aiclient import world_identity` (or `from tw2002_aiclient.world_identity import …`) works
2. `world_id` / `world_id_from_profile` match archive contract (determinism, host lowercasing, anti-galaxy-bleed across handle/game/host, `WorldIdentityError` on empty components) — existing test suite green after import fix
3. `pytest tests/test_world_identity.py -q -n0` pass
4. Zero product callers required yet (L2 consumes)

## Proof

```text
pytest tests/test_world_identity.py -q -n0
```

## Refs

- `canon/engine/world-identity.md`
- `archive/pre-rebirth-2026-07-23/code/twclient/world_identity.py`
- `tw2002_aiclient/world_model.py` (comments already point at world_identity)
