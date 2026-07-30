# WO-CHAIN-BUBBLE-PORT-CLASSES

**Status:** READY  
**Depends:** `main` ≥ `fb33f5b` · `WO-PLAY-CHAIN-BUBBLE-VIZ` (#256)

## Goal

Enrich the always-on chain-bubble strip so sector class labels are real
(e.g. `BBS`) instead of perpetual `?`, and so the port-only filter can drop
non-port hops when world-model port data is available.

## Why

#256 shipped the cache hooks (`ChainScalars.port_classes`) and composer
APIs (`port_classes`, `known_ports`) but `update()` never fills
`_port_classes`, and `screens.py` does not pass `known_ports`. Result:
bubbles always show `?` class rows even after priced ports are known.

## Scope (explicit paths)

- `tw2002_aiclient/chain_status.py` — on successful non-empty `update()`,
  derive `sector → class` (and optionally expose `known_ports`) from the
  existing world-model / trade-adapter port records for that world. Failed /
  truncated / no-world updates must not invent classes; completed empty
  clears as today. Never put the class map on daemon `status` JSON.
- Call sites that already invoke `chain_scalars.update(discovered)`
  (`cockpit/live_refresh.py`, Play `L` path in `app.py` if needed) — pass
  whatever world_id / state_dir context `update` needs without draw-path
  filesystem reads.
- `tw2002_aiclient/screens.py` — pass `known_ports` (from the cache) into
  `compose_chain_bubbles` alongside `port_classes`.
- Tests: `tests/test_chain_status_coach_wire.py`,
  `tests/test_play_chain_bubbles_visible.py`, and/or a focused new pin —
  synthetic world with known port classes paints those labels; missing
  class stays `?`; non-port hop filtered when `known_ports` is set.

## Out of scope

- New discovery / recompute algorithms.
- Arming chains from bubbles.
- Daemon protocol / `status` schema changes.
- Broader cockpit redesign.

## Accept

1. After a successful discovery over a world with class-bearing port
   records, `chain_scalars.port_classes` contains those sector→class
   entries and bubble class row shows them (not `?`).
2. Sectors without a known class still render `?` (honest partial).
3. When known ports exist, `compose_chain_bubbles(..., known_ports=…)`
   drops non-port hops (existing filter semantics).
4. Failed/truncated/no-world updates do not fabricate class maps; last
   good classes retained with the last good chain (mirror best_chain
   retention) **or** documented same-clear policy with a pin — pick one
   and pin it.
5. Draw path still does not import `chain_search` / `world_model`.
6. Focused tests + full offline suite green.
7. live-prove: `n/a` (chrome enrichment / offline pins).

## Proof

```bash
pytest -q tests/test_chain_status_coach_wire.py \
  tests/test_cockpit_chain_bubbles.py \
  tests/test_play_chain_bubbles_visible.py
pytest -q -m "not live_login and not pty_ui"
```

## Seat notes

- Prefer reading existing world-model port `class` fields
  (`trade_adapter` / `world_model.all_sectors` patterns) — do not invent a
  second store.
- Do not touch shared operator `run/`.
- CLAIM → exclusive WT on HANDOFF branch → STATUS-DONE.
- Hub WT idle at `/private/tmp/hub-chain-bubble-port-classes`.

## Refs

- #256 honest gap · plan
  `trade-loop-chain-visibility-2026-07-30.md` Slice 2 follow-on
- `explore.known_port_sectors` · `trade_adapter._class_ports`
