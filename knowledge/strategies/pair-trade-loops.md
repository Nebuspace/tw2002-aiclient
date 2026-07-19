---
type: Strategy
title: Pair Trade Loops
description: Cycle between two (or more) complementary ports that buy and sell opposite commodities, scoring profitability by credits-per-turn rather than credits-per-trip.
tags: [strategy, trading, ports, core-strategy]
timestamp: 2026-07-19T16:11:33Z
---

A pair trade loop is the base unit of TW2002 income: two sectors whose ports have complementary
commodity postures (one buys what the other sells) close together on the warp graph, worked
repeatedly.

# What it is
- Two (or more) ports where Port A sells a commodity Port B buys, and vice versa — or a port
  paired with a co-located planet acting as the second leg.
- The pilot alternates: buy low at A → move to B → sell, buy B's cheap commodity → move back to
  A → sell. The "loop" is the repeating cycle, not a single trade.

# When it applies
- Whenever the world-model (see [World Model](/architecture/world-model.md)) has identified two
  nearby ports with a positive spread on at least one commodity in each direction.
- Preferred over one-off trades because travel turns between the same two sectors amortize across
  every future cycle — the first trip pays for itself; every rotation after is close to pure
  margin minus commodity cost.

# Tradeoffs
- **Score by credits-per-TURN, not credits-per-trip.** A loop with a smaller net profit but fewer
  turns per cycle can out-earn a bigger, slower loop. Treat turns-per-cycle as a first-class
  ranking input alongside net credits, and rank candidate loops by credits/turn rather than raw
  credits/trip.
- **A loop is not infinite.** A port's tradeable stock is finite and depletes as you buy/sell
  against it; running the same loop past its useful life burns turns for shrinking margin instead
  of rotating to a fresh one — see [Port Economics](/strategies/port-economics.md) for the
  stock-sustainability model this depends on.
- **Loop shape sets the turn floor.** An adjacent port pair (one warp-hop each way) is a cheap loop
  shape by hop-count; a port co-located with your own planet (a planet-side sale, no second travel
  leg) removes a leg entirely. The actual turn cost of any hop also depends on the ship flown — see
  [TW2002 Ships and Equipment](/reference/tw2002-ships-and-equipment.md) for how turns-per-warp
  varies by ship and changes this math.
- **Haggling is a per-trade decision layered on top of a loop, not a property of the loop itself.**
  Whether to negotiate a better price or accept the posted one trades turns/attempts spent
  negotiating against the marginal credits gained; a bounded, deterministic negotiation policy that
  converges within a capped number of rounds avoids burning time chasing a few extra credits. See
  [Toll and Defense Math](/strategies/toll-and-defense-math.md) for the general "is this worth the
  turns" framing this borrows from.

# Steps
1. Identify a candidate pair via the world-model or direct exploration: two nearby ports (or a
   port + your own planet) with opposite buy/sell postures on at least one commodity each.
2. Estimate the loop's turns-per-cycle and expected profit-per-cycle; rank candidates by
   credits-per-turn (see [Port Economics](/strategies/port-economics.md) for the price/spread and
   stock model this estimate depends on).
3. Work the loop: buy → travel → sell/buy → travel → sell, repeating.
4. Track the loop's remaining useful life against stock depletion — a loop nearing depletion should
   be rotated out, not run to zero.
5. When a loop's depletion signal fires, fall back to exploration (see
   [Frontier Exploration](/strategies/exploration.md)) to discover a fresh replacement rather than
   continuing to run a decayed loop.

# Examples
```
Loop shape A — adjacent pair:
  Port X sells Equipment, buys Fuel Ore
  Port Y sells Fuel Ore, buys Equipment
  One warp-hop each way — the cheapest possible loop shape by hop-count; actual turn
  cost still depends on the ship's turns-per-warp.

Loop shape B — port + co-located planet:
  Buy cheap at the port, ferry to your adjacent planet, the planet consumes/sells —
  no second travel leg, so this shape removes a full hop from the cycle versus shape A.
```

# Citations
[1] design history §16.2 — profit-per-turn scoring, adjacent-pair vs planet-side loop shape
[2] design history §8 — live-play finding that a depleting loop should trigger exploration for a
    replacement rather than be abandoned outright
