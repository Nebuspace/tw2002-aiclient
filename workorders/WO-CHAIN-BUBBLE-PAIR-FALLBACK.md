# WO-CHAIN-BUBBLE-PAIR-FALLBACK — show class pair loops when profit bubbles are empty

**Status:** DONE · origin `91fa979` (#269) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/CHAIN-BUBBLE-PAIR-FALLBACK`
**Depends:** `main` ≥ `dfc560f` (#256/#257 bubbles + #265 gather)

## Symptom (operator)

Play's always-on chain-bubble strip stays at `○ ○  no trade loop yet` while
exploring past many ports. Measured on live academy world
`tradewarsacademy_com__A__Sextant` (2026-07-31):

| Signal | Count |
|---|---|
| sectors | 61 |
| ports with class | 39 |
| ports with docked commodities | 8 |
| `tw pairs` candidate pair loops | dozens |
| `build_trade_hops` | 24 hops, **every margin = 0.0** |
| `chain_search.recompute` | `chains=()` · `reason=no_closed_cycle` |

Root cause (two layers, both real):

1. **Bubbles only paint `ChainScalars.best_chain`** — a positive-margin
   `ProfitChain` from `chain_search`. Class-derived `CandidatePair`s from
   `chain_detect` / `tw pairs` never reach the strip.
2. **Pricing model collapses after Gather:** every fresh dock writes
   `pct=100` on all rows; `_commodity_price` is posture-blind (same curve
   for buying and selling), so `to_price - frm_price` is always `0` when
   both sides share the same pct. `chains.find_profit_chains` hard-filters
   `margin > 0` → empty forever until pcts diverge (often never, early
   explore).

Passing ports is enough for **pair** topology; it is not enough for a
**priced** cycle under today's estimator. The empty placeholder is
therefore dishonest when pairs exist.

## Goal

When no positive-margin best chain is available, the always-on bubble strip
falls back to the best class-derived pair loop (or honest empty only when
pairs are also absent). Operator must see a loop as soon as complementary
port classes + routes are known — without waiting for pct diversity.

## Scope

1. **`chain_status.py` / live refresh / `L` open path** — retain a
   `best_pair` (or equivalent) from `chain_detect.recompute` / candidate
   pairs alongside `best_chain`. Failed/truncated updates must not invent
   pairs; retention policy mirrors `best_chain` (document + pin).
2. **`screens.py` / `compose_chain_bubbles` call site** — paint
   `best_chain` when present; else paint the fallback pair as a 2-hop
   bubble cycle (sectors A↔B). Empty placeholder only when both absent.
3. **Honest chrome** — visually or via status/coach distinguish
   "priced profit cycle" vs "class pair (unpriced)" if cheap (label row /
   different empty-vs-pair copy). Do not claim credits/turn for class pairs.
4. **Tests** — synthetic: ports with classes + route, no commodities →
   bubbles show pair; with positive-margin chain → chain wins; neither →
   `○ ○  no trade loop yet`.
5. **Optional follow-on bank only (out of this Accept):** buy/sell spread
   in `trade_adapter._commodity_price` so same-pct docks can produce
   `margin > 0`. Do **not** invent spread numbers in this WO without a
   named config knob + pin; prefer separate WO if touched.

## Out of scope

- Arming / approving pairs from the bubble strip.
- Changing `chains.py` `margin > 0` canon filter.
- `#218` app.py split.
- Sacrificial turn-spend live arms beyond safe observation.

## Constraints

- Draw path still must not import `chain_search` / `world_model` / heavy
  finder (keep compute on idle refresh + `L`, cache on `ChainScalars`).
- Class pairs carry **no margin** — never mint `0.0` margin onto them.
- Public-safe STATUS (host-key nicknames only).

## Accept

1. Live or fixture world with complementary class ports and known routes,
   **without** commodity pct diversity, paints a non-empty bubble pair
   (not the empty placeholder).
2. When a positive-margin `ProfitChain` exists, bubbles prefer it over the
   pair fallback.
3. When neither chain nor pair exists, placeholder remains
   `○ ○  no trade loop yet`.
4. Focused tests + full offline suite green.
5. Live-prove: Cursor — safe half: after Gather/Explore on ≥1 host (or
   existing world with pairs), screenshot/status that bubbles are non-empty
   OR honest `pairs=0` evidence. Diversity preferred; SKIP with reason OK.

## Proof

```bash
pytest -q tests/test_chain_status_coach_wire.py \
  tests/test_cockpit_chain_bubbles.py \
  tests/test_play_chain_bubbles_visible.py
# + any new focused pins
pytest -q -m "not live_login and not pty_ui"
```

Live: DEFERRED → Cursor after suite.

## Refs

- Max live-report 2026-07-31 (`○ ○  no trade loop yet` despite ports)
- `tw2002_aiclient/cockpit/chain_bubbles.py` · `chain_status.py` ·
  `cockpit/live_refresh.py` · `trade_adapter.py` · `chain_detect.py` ·
  `chains.py` (`margin > 0`)
- Measured: academy Sextant · `reason=no_closed_cycle` · 24 zero-margin hops ·
  many `tw pairs` rows
- Canon: `canon/strategy/trade-loops.md` (TradeHop = positive-margin) ·
  DECISIONS class-derived `CandidatePair` path
