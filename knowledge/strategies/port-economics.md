---
type: Reference
title: Port Economics
description: Port classification, price-spread behavior, stock/regrowth dynamics, and floor-price concepts that determine how sustainable and how profitable a given trade loop is.
tags: [reference, trading, ports, hypothesis]
timestamp: 2026-07-19T16:11:33Z
---

**Verification status:** UNVERIFIED against the live game. Every specific number in this document
(floor prices, regrowth rate, plague-threshold stock level) is carried over from third-party
TW2002-variant strategy-guide research and MUST be confirmed against direct in-game observation
before being treated as fact. Encode these as configurable parameters, never hardcoded constants,
until verified.

# Port classification
Each port trades a small set of commodities and, for each, holds one posture: buying or selling. A
port's classification for strategy purposes is:
- Which commodity(ies) it sells (a source leg for a loop) vs buys (a sink leg).
- Its per-hold price spread on each commodity — the gap between what it pays/charges near full
  stock vs near-empty stock.
- Its distance-to-floor — how close its current price sits to that commodity's theoretical floor
  price.

# Commodity floor prices (hypothesis)
| Commodity | Hypothesized floor price (credits/unit) |
|---|---|
| Ore | 20 |
| Organics | 30 |
| Equipment | 40 |

Equipment's higher floor makes it the premium commodity of the three — all else equal, a loop
ending in an Equipment SELL leg is hypothesized to out-earn an equivalent Ore or Organics loop.
Confirm the floor values above against the live game before relying on this preference; see
[Pair Trade Loops](/strategies/pair-trade-loops.md) for how loop candidates are ranked.

# Stock and regrowth model (hypothesis)
- A port's tradeable stock for each commodity depletes as it is bought/sold against.
- Hypothesized regrowth: stock recovers at roughly 10% per day of real time while not actively
  traded — meaning a loop should be **revisited on a rotation, not abandoned** the first time it
  looks thin.
- **Route-longevity estimate:** remaining trades on a loop before depletion is hypothesized as the
  smallest of the four buy/sell stock fields, divided by your ship's hold count. That figure
  falling toward zero is the rotate-out signal.
- **Plague/inventory-crash risk (hypothesis):** total stock approaching a very large ceiling (on
  the order of 10 million units, per the source material) is described as an imminent
  inventory-crash ("plague") condition to avoid — unverified locally; treat as a warning heuristic,
  not a hard limit, until confirmed.

# Citations
[1] design history §16 — load-bearing flag: every specific number in this document is
    community/strategy-guide-derived and unverified against the live game
[2] design history §16.2 — regrowth rate, route-longevity formula, floor prices, plague-ceiling
    heuristic
