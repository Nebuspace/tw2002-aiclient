# WO-FIX-CHAIN-STATUS-UPDATE-COMMODITY-MAP-NAMEERROR

**Priority:** HIGH  
**Claimed-by:** impl-aiclient-h1

## Goal

`ChainScalars.update()` unpacked `cmap` from `_port_snapshot_from_world` then
assigned `self._commodity_maps = commodities` — `commodities` undefined →
`NameError` swallowed by `except Exception: pass`, so commodity maps never
populated via `update()`.

## Fix

Rename unpack target to `commodities` (match sibling `update_pairs()`).

## Accept

- [x] No NameError on successful update with world commodities
- [x] Regression test pins `_commodity_maps` populated
- live-prove: n/a (offline NameError; enrichment path unit-tested)

## Proof

```bash
.venv/bin/python -m pytest tests/test_chain_status_coach_wire.py -q -n0 -k commodity_maps
```
