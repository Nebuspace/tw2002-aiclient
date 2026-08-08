# WO-BUILD-PORT-FLOOR-PRICE-LIVE-CAPTURE

**Goal:** `canon/strategy/port-economics.md`'s Floor-price/regrowth section
flags every floor-price and regrowth-rate figure as an UNCONFIRMED HYPOTHESIS
with **zero code backing** — `state_parser`/`world_model` persist only
`amount`+`pct`+`class` per port visit, nothing about how those figures move
over repeated visits to the same port over time. This WO builds the missing
analysis step: given a sequence of observations of the SAME port/commodity
collected over time, turn them into a measured regrowth-rate and floor-price
**estimate**, so a future capture loop has something to feed and the coach/
priority layer eventually has a real (labelled, still-unverified-until-live)
number to compare against `port_economics.py`'s hardcoded hypothesis
constants.

**Scope:**
- `tw2002_aiclient/port_floor_capture.py` — new. Pure analysis module:
  `PortObservation` input dataclass, `estimate_regrowth_rate`,
  `estimate_floor_price`, `analyze_port_history` convenience wrapper. No
  socket I/O, no live-send, no auto-visiting a port, no scheduling — a
  future capture loop (out of scope here) is the thing that would collect
  real `PortObservation` rows and call into this module.
- `tests/test_port_floor_capture.py` — new. SYNTHETIC fixtures only (see
  Out of scope / live-data caveat below).
- this WO file.

**Out of scope:**
- **No live data was collected.** This WO builds and proves the *analysis
  capability* against hand-authored synthetic fixtures (declining/regrowing
  port stock over fabricated timestamps). It does **not** collect, and does
  not claim to have collected, a real multi-visit sample against an actual
  TWGS server. No number in this module's tests or docstrings is presented
  as a measured live fact — every result the module returns carries
  `tag="observed_estimate"` and `verified_vs_live=False` regardless of input
  provenance, and the caller is responsible for knowing whether its inputs
  were real or synthetic.
- **No capture loop.** Wiring this analysis module into an actual repeated-
  visit capture cycle (deciding when to revisit a port, persisting
  `PortObservation` rows to disk, correlating with `world_model`'s existing
  per-sector `port` record) is a separate WO. This module only consumes
  whatever a future capture loop hands it.
- **No change to `port_economics.py`'s hypothesis constants.** The existing
  `FLOOR_PRICES` / `REGROWTH_PCT_PER_DAY` `HypothesisParam` values are
  untouched; this module does not flip `verified_vs_live` on them or on
  anything else. That flip is a live-prove decision for whoever eventually
  runs the capture loop against a real server, not this WO.
- **No price-quote reader.** `estimate_floor_price` consumes an optional
  `price_per_unit` per observation, sourced today from a completed haggle's
  `final_price` (`session/haggle.py`) when one happens to occur on that
  commodity at that visit. Building a dedicated price-quote screen reader is
  out of scope; this WO takes whatever price observations already exist.

**Constraints:**
- Regrowth is only computed over observation pairs the caller explicitly
  marks `traded_since_prior=False` on the later observation — an amount/pct
  rise with `traded_since_prior=None` (unknown) or `True` (the operator
  themself traded) is excluded rather than guessed, since the module cannot
  otherwise distinguish organic regrowth from a trade-caused change.
- Floor price is a linear fit of observed `price_per_unit` against `pct`
  evaluated at `pct=100` (canon: "the price a commodity's value decays
  toward as a port's stock fills") — requires at least two distinctly-priced,
  distinctly-`pct` observations; degenerate/insufficient input is omitted
  from the result, never a fabricated single-point estimate.
- Identities are segregated by `(sector_id, port_id, commodity)` so a mixed
  batch of observations across multiple ports/commodities never cross-
  contaminates one estimate with another's readings.
- Never raises on malformed/insufficient input — an identity with no
  qualifying pairs/observations is simply absent from the result dict.

**Accept:**
1. `estimate_regrowth_rate` correctly averages pct-per-day across trade-free
   rising pairs, per `(sector_id, port_id, commodity)`.
2. `estimate_floor_price` correctly linear-fits price-vs-pct and evaluates
   at pct=100, requiring ≥2 priced, distinctly-`pct` observations.
3. Both functions segregate by sector/port/commodity identity and never
   fabricate an estimate from insufficient data.
4. `analyze_port_history` combines both into one report; every returned
   estimate carries `tag="observed_estimate"` and `verified_vs_live=False`.

**Proof:** `.venv/bin/python -m pytest tests/test_port_floor_capture.py -n0 -q`
→ 12 passed.

**Live-prove status: DEFERRED.** This WO's build + proof is against
synthetic fixtures only (per this repo's Claude-Code-defers-live-prove
convention). No real multi-visit port observation has been collected against
a live TWGS server. Before `canon/engine/priority-engine.md` (or any other
consumer) may cite a *specific* regrowth/floor number as a confirmed fact
rather than a hypothesis, a follow-up live-prove pass — collecting real
`PortObservation` rows from an actual server session and running them
through this module — is required.
