# WO-BUILD-DENSITY-SCAN-VALUE-TABLE-PARSER

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** MED (Cycle-43)  
**Depends-on:** none (pure parser; writeback deferred)

## Goal

Land a fail-closed density / holographic scan interpreter: extract `sector → density_value`
from scan screen text, expose the canon value-table atoms, and tip-stamp
`canon/engine/world-model.md` that the raw parser is LIVE while grammar + writeback remain
provisional.

## Scope

- `tw2002_aiclient/density_scan.py` — `parse_density_scan(text) -> dict[int, int]` + `DENSITY_VALUE_TABLE`
- `tests/test_density_scan.py` — synthetic fixtures (colon / arrow / last-match / fail-closed)
- `canon/engine/world-model.md` — tip-stamp interpreter LIVE; writeback still unlanded

## Out of scope

- World-model upsert / presence-via-absence decoding
- Live TWGS density-scan capture
- Autopilot / keystroke senders
- Decoding cumulative density into atom sets (callers may use the table later)

## Accept

1. `parse_density_scan` returns `{sector: density}` on synthetic multi-row text; last match wins per sector.
2. Non-string / junk / StarDock product-listing noise → `{}` (fail-closed).
3. `DENSITY_VALUE_TABLE` matches canon atoms `1/5/10/40/100/500`.
4. Canon divergence paragraph no longer claims “no density-scan interpreter wired.”
5. Offline: `pytest tests/test_density_scan.py` green.

## Proof

```bash
.venv/bin/python -m pytest tests/test_density_scan.py -q
```

Live-prove: **n/a** (pure offline parser + docs tip-stamp; no session / login / play path).
