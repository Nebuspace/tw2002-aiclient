# WO-CATALOG-SOURCE-LIVENESS-SPLIT — Separate provenance from TCP liveness

**Status:** BANKED · MED · Cursor-class (or CC) · execute after #128 Accept preferred (not blocking)  
**Posted:** 2026-07-28T02:31Z · hub bank from CC live-prove probe (#128 diversity prep)  
**Seat:** open · docs bank first; EXEC when a seat is free  
**Refs:** CC STATUS ~2026-07-28T02:04Z · `config/servers.inventory.json` · live-prove-pushback

## Goal
Catalog `status` today conflates **listing provenance** (`listed` / `listed_bbsguide`) with **reachability**. Hub/seat live-prove planning treated `connectable: 0` as “no TWGS” while a safe TCP sample showed many listed hosts open. Split fields so operators and scripts cannot confuse source with liveness.

## Scope
- `config/servers.inventory.json` (+ any loader / summary that prints `connectable`)
- Optional mirror notes in `servers.toml` description convention (no secret/host runbooks)
- Safe TCP seed script or documented one-shot probe that writes `liveness` + `last_probed_utc` only (no game turns)

## Accept
1. Schema/docs: distinct **source/provenance** vs **liveness** (+ `last_probed_utc`); `status=listed*` no longer implies down/up.
2. Aggregates that currently report `connectable: 0` from provenance alone are fixed or removed.
3. Pin: inventory with `source=listed` + `liveness=unreachable` (or unset) does not count as “no hosts exist” for live-prove planning helpers.
4. Suite + STATUS; live-prove of the probe itself = safe TCP sample (hub GO; no arm).

## Constraints
Public-repo safe — no tailnet IPs, credentials, or connection runbooks. Do not widen #128. Do not invent game-letter / M6–M7 work here.
