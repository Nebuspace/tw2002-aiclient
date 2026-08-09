# WO-BUILD-PLANET-COLONIZATION-LIVE-CAPTURE

**Status:** READY FOR REVIEW
**Priority:** LOW
**Gated:** no (capture/store is filesystem-only; live planet-screen collection DEFERRED)

## Goal

`canon/strategy/planet-colonization.md` Verification / hypothesis sections (~lines 151–175)
flag every production number — stored-cargo bonus, compounding rate, buy-production threshold,
plague band, GF-growth curve — as **UNCONFIRMED HYPOTHESIS with no implementing module**.
This WO builds the missing **capture-and-confirm analysis step** mirroring
`port_floor_capture.py`, without wiring estimates into live recommendations.

## Scope

- `tw2002_aiclient/planet_colonization_capture.py` — pure analysis:
  `PlanetObservation`, five estimators, `analyze_planet_history`, JSONL store helpers.
- `tw2002_aiclient/planet_colonization_cli.py` — `tw planet-colonization {snapshot,analyze}`.
- `tests/test_planet_colonization_capture.py` — synthetic fixtures only.
- Canon stamp in `canon/strategy/planet-colonization.md` (module exists; numbers stay hypothesis).

## Out of scope

- Live TWGS drive to collect real planet screens (DEFERRED).
- Wiring estimators into `formations.py` recommend scoring.
- Flipping any hypothesis to `verified_vs_live=True`.

## Accept

1. Analysis module with observation dataclasses + estimators for bonus rate, compounding rate,
   buy-production threshold, plague band, GF-growth curve — or honest omission when data cannot
   support a fit.
2. Every estimate carries `tag="observed_estimate"` and `verified_vs_live=False`.
3. `tw planet-colonization snapshot|analyze` registered and filesystem-only.
4. Synthetic-fixture tests green.
5. Canon documents module existence; hypothesis numbers remain unverified vs live.

## Proof

```
.venv/bin/python -m pytest tests/test_planet_colonization_capture.py tests/test_cli_log.py -n0 -q
```

## Refs

- `canon/strategy/planet-colonization.md` Verification status · Code divergence
- `tw2002_aiclient/port_floor_capture.py` — precedent pattern
- WO-AI-TRANCHE-5 item 1
