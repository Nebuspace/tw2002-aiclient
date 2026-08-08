# WO-BUILD-PORT-FLOOR-PRICE-LIVE-CAPTURE

**Status:** PARTIAL — analysis module LIVE (#530); capture-loop + live seed on this branch
**Priority:** MED
**Gated:** no (capture/store is filesystem-only; turn-spend multi-visit still Max-gated when TL>0)

## Goal

`canon/strategy/port-economics.md`'s Floor-price/regrowth section
flags every floor-price and regrowth-rate figure as an UNCONFIRMED HYPOTHESIS
with **zero code backing** — `state_parser`/`world_model` persist only
`amount`+`pct`+`class` per port visit, nothing about how those figures move
over repeated visits to the same port over time. This WO builds the missing
analysis step **and** the observation capture path that feeds it.

## Shipped slices

### A — Analysis module (PR #530, merged)

- `tw2002_aiclient/port_floor_capture.py` — pure analysis:
  `PortObservation`, `estimate_regrowth_rate`, `estimate_floor_price`,
  `analyze_port_history`. Synthetic-fixture tests only.
- Every estimate carries `tag="observed_estimate"` and
  `verified_vs_live=False`. `port_economics.py` hypothesis constants
  untouched.

### B — Capture loop + live seed (this branch · Cursor IDLE-KICK)

- JSONL observation store (`state/port_floor_observations.jsonl` by default)
  with load/append + world-dir ingest helpers on the same module.
- Best-effort append-on-write hook from `world_model.write_from_state` /
  `write_port_only` when commodities are present (`traded_since_prior=None`).
- `tw port-floor snapshot|analyze` CLI (`port_floor_cli.py`) — filesystem
  only, never sends.
- Live-derived seed fixture: `tests/fixtures/port_floor_live_seed.jsonl`
  (≤30 rows from real `state/world` port records; varied pct; no secrets).

**Live-prove (this slice):**

- TCP sample: 8/8 catalog hosts OPEN (academy, a-net, constructivechaos, …).
- Daemon connected `tradewarsacademy.com` / `scout_academy`
  (`crawl_sacrificial=true`) at `main_command` sector 1214 — **TL=00:00:00**
  so same-day re-dock / multi-visit regrowth collection is **blocked** (no
  turn-spend).
- Seed ingest from live-derived world-model files is real TWGS-sourced
  `amount`/`pct`/`last_seen_ts` data, but **one snapshot per sector** →
  `analyze` correctly returns **zero** regrowth/floor estimates (needs
  multi-visit pairs with `traded_since_prior=False` and/or priced
  observations). That empty result is honest, not a bug.
- Follow-up when turns refresh: re-visit depleted ports without trading,
  append observations (hook or `tw port-floor snapshot`), re-run analyze.
  Do **not** flip `port_economics` `verified_vs_live` until a measured
  multi-visit sample exists.

## Out of scope (still)

- Flipping `port_economics.py` hypothesis `verified_vs_live`.
- Feeding priority-engine scoring from these estimates.
- Dedicated price-quote screen reader (still optional `price_per_unit` from
  haggle when present).

## Accept (updated)

1–4. Analysis Accept from #530 — still hold.
5. Observation store round-trips; world_model commodity writes append rows.
6. `tw port-floor snapshot|analyze` registered and filesystem-only.
7. Live-derived seed fixture committed; analyze report posted (may be empty
   estimates with reason).

## Proof

```
.venv/bin/python -m pytest tests/test_port_floor_capture.py -n0 -q
```

## Refs

- `canon/strategy/port-economics.md` Floor-price section
- Hub ACK #530: live-capture deferred to Cursor
