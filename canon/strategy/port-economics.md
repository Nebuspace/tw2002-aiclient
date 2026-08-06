---
type: Reference
title: Port Economics — Classification, Spread & Depletion
description: The numeric parameter substrate — port classification, per-hold price spread, floor-price and regrowth model, and the depletion/route-longevity predictor — that trade scoring and trade rule-guards read, never a live action-picker.
tags: [reference, strategy, trading, ports, spread, depletion, hypothesis, read-only-substrate]
timestamp: 2026-07-23T20:20:02Z
---

> **Verification status:** UNVERIFIED against the live game. Every specific number below — floor
> prices, regrowth rate, plague/inventory-crash ceiling — is carried over from third-party
> TW2002-variant strategy-guide research and MUST be confirmed against direct in-game observation
> before being treated as fact. Each is a **configurable coaching/guard parameter**, never a
> hardcoded constant, and the concrete per-server values are introspected live into the
> [Game-Data Store](/engine/game-data-store.md) — this document authors the portable *model shape*
> (there is a floor; Equipment's floor sits above Organics' above Fuel Ore's; stock depletes and
> regrows), not the server's actual numbers. The hypothesis discipline is itself a safety rule (see
> its own section below).

Port economics is a **read-only parameter substrate**, not a behavior. It describes how to score a
port's worth to a trade loop and how to predict when a loop dies — figures that
[Trade Loops](/strategy/trade-loops.md) and the [Priority Engine](/engine/priority-engine.md)
*read* to rank which taught loop the human is coached toward or which the app replays next. Nothing
here emits a keystroke, and — the load-bearing reborn framing — nothing here lets a computed number
override the runtime invariants. The priority layer that consumes this substrate **ranks and
orders** taught behaviors; it is never a live per-cycle action-picker that lets an expected-value
computation win over an unrecognized screen. On any screen the app does not recognize it STOPS and
hands the human the keyboard, every cycle, regardless of how profitable a loop the numbers below say
sits one warp away. This document is prescriptive spec feeding rule-guards, priority scoring, and
human coaching — not a driver.

# Schema

## What the client actually observes (grounded in code)

Before any hypothesized economics, fix what the parser genuinely reads off a port screen, because
the model must be expressed in those terms. `state_parser.parse_state` extracts, per commodity, a
row of `{name, status, amount, pct}`:

| Field | Meaning | Source |
|---|---|---|
| `name` | One of `Fuel Ore`, `Organics`, `Equipment` (the three tradeable commodities). | `COMMERCE_COMMODITIES` in `state_parser.py`. |
| `status` | `buying` or `selling` — the port's posture on that commodity (a **buying** leg is a sink for the player, a **selling** leg a source). | commodity-row regex. |
| `amount` | The port's current **trading amount** in units (the raw stock figure, e.g. `2650`). | second column of the trade row. |
| `pct` | **% of max** — how full that commodity's stock sits relative to its own ceiling (0–100). | the `%`-suffixed column. |

A port's three-letter class code (`BSB`, `SBS`, …) encodes the same postures compactly: first
letter = Fuel Ore, second = Organics, third = Equipment; `B` = buying, `S` = selling. The
[World Model](/engine/world-model.md) persists `port: {class, commodities:[{name, status, amount,
pct}], last_seen_ts}` per sector — that stored record *is* the profit database this document scores
against. Note the commodity is named **`Fuel Ore`** in code (legacy strategy notes said "Ore"); use
the code's name so a scored figure keys to a real stored row.

## Port classification for scoring

A port's worth to a loop is characterized by four figures, all derived from the observed row above:

- **Sell-commodity (the source/sink posture)** — which commodity(ies) it *sells* (a source leg you
  buy from) versus *buys* (a sink leg you sell into). A pair-trade loop needs one port selling what
  the other buys; see [Trade Loops](/strategy/trade-loops.md) for how legs are matched.
- **Per-hold price spread** — the gap, per commodity, between the price near full stock and near
  empty. The wider the spread the more a single round-trip earns per hold. The spread is a
  *behavioral* property of the port (how hard its price moves with stock), read from repeated
  observations, not a single reading.
- **Distance-to-floor** — how close the current price sits to that commodity's theoretical floor
  (below). A port already near its floor has little spread left to give; a port far from floor is
  the richer leg. `pct` (% of max) is the observable proxy the client actually has for this until a
  live floor price is confirmed.
- **Plague-ceiling proximity** — how close total stock sits to the inventory-crash ceiling
  (below) — a *hazard* input, not a profit input.

**Equipment is the premium commodity (H3, hypothesis).** Its higher hypothesized floor makes an
Equipment **sell** leg out-earn an equivalent Fuel Ore or Organics leg, all else equal — so a loop
ending in an Equipment sell is preferred *as a ranking input*, never as a reason to override a STOP.
Confirm the floor values before relying on this preference.

## Floor-price model (hypothesis)

The floor is the price a commodity's value decays toward as a port's stock of it fills. The
**portable semantic** is only the ordering — Equipment's floor sits above Organics', above Fuel Ore's.
The concrete credits/unit figures are unverified starting hypotheses, to be confirmed or introspected
per server, never authored as fact:

| Commodity | Hypothesized floor (credits/unit) [hypothesis] |
|---|---|
| Fuel Ore | 20 |
| Organics | 30 |
| Equipment | 40 |

**Regrowth (hypothesis):** a port's stock of each commodity recovers at roughly **~10% per day** of
real time while it is not actively traded [hypothesis]. The strategic consequence is prescriptive: a
loop that looks thin should be **revisited on a rotation, not written off** the first time its stock
reads low — but "rotate, don't abandon" is a principle for the human and the priority ranking, **not
a license for the app to autonomously switch loops** (see Depletion, below).

## Route-longevity & depletion predictor (H2, hypothesis)

How many more round-trips a loop yields before it depletes is hypothesized as:

```
remaining_trades  ≈  min(stock across the loop's four buy/sell legs)  ÷  ship hold count
```

where hold count comes from the live [Game-Data Store](/engine/game-data-store.md) (never
hardcoded), and the four leg stocks are the observed `amount` fields of the two ports' relevant
commodities. As `remaining_trades` falls toward zero the loop is nearing depletion.

**Depletion is a STOP-guard, not an autonomous rotation.** In the reborn runtime, a loop reading
depleted (or a **plague/inventory-crash** condition — total stock approaching a very large ceiling,
hypothesized on the order of **~10 million units** [hypothesis], an imminent-crash warning heuristic
to *avoid*, not a hard limit) is a **signal**, and the signal does exactly two prescribed things:

1. It **STOPS the taught loop and escalates to the human** — the app does not silently rotate the
   ship onto a different loop on its own authority. A depletion or hazard guard hands control back;
   the human (or a human-armed re-selection) decides what runs next. Depletion must never trigger a
   quiet autonomous route swap.
2. It **raises the exploration appetite** as a priority input (see
   [Exploration Policy](/strategy/exploration-policy.md) — depletion is a demand-driven reason to
   explore for fresh loops), and **down-ranks** the depleted loop in the priority ordering so the
   human is coached toward alternatives. Ranking, not driving.

The "rotate-don't-abandon" wisdom survives intact as *strategy* — it tells the human and the ranking
layer that a thin loop is worth a later revisit rather than a permanent write-off. What it does not
do, in the reborn framing, is authorize the app to keep itself busy by rotating loops autonomously.

## The hypothesis discipline as a safety rule

Treating every number here as a labelled, configurable, verify-before-trust hypothesis is not
bookkeeping — it is a safety guard. A hardcoded floor price or regrowth rate that silently disagreed
with the live server would feed a wrong figure into a loop-ranking or a depletion prediction the
human is trusting: a bad decision dressed as authored fact. Encode these as parameters, tag them
`hypothesis`, carry the Verification-status line, and let the concrete values enter only by live
introspection. **Docs win:** where the code diverges from this substrate, record the divergence (see
below) — never silently conform the doc to the code.

# Examples

- **Ranking two candidate loops.** Loop A ends in an Equipment sell far from floor with wide `pct`
  headroom on all four legs; Loop B ends in a Fuel Ore sell already near floor with one leg at low
  `amount`. The priority engine reads this substrate and *ranks A above B* — surfaces A as the
  coached/replayed loop first. It does **not** send a keystroke toward A; it orders a suggestion.
- **A loop hits depletion mid-run.** The predicted `remaining_trades` on the active loop crosses
  toward zero. The depletion guard STOPS and escalates, raises explore appetite, and down-ranks the
  loop — it does **not** pick a fresh loop and drive to it. The human is handed the decision.
- **An unrecognized screen appears while a rich loop sits one warp away.** Irrelevant to this
  substrate: the app STOPS on the unknown frame regardless of any expected value the numbers here
  compute. Economics never outranks stop-on-unknown.

# Code divergence

Recorded per DOCS WIN — the reborn target above is the spec. Tip gaps below must be brought to the
doc; **archive-only** shapes are do-not-revive (not open tip defects to "fix"):

- **Archived autopilot per-cycle EV select + `EXPLORE_BASELINE_EV` "never idle" — do-not-revive.**
  Pre-rebirth `twclient/autopilot.py` consumed economic figures as a live per-cycle EV action-picker
  with a baseline explore floor that kept driving. That module is **gone from tip**. These numbers
  feed *ranking, guards, and coaching only*; depletion/idle is a STOP-guard, not a reason to keep
  the ship moving. See [app-autopilot-model](/architecture/app-autopilot-model.md).
- **`trade_driver` autonomous chain runner.** Tip trade driver can still run a trade chain across
  sectors under arm/guards. The reborn target requires stop-on-unknown re-validated **every
  cycle** and a **human-armed** loop before any background run — a chain is a taught behavior the
  human arms, not a self-launching runner.
- **§22 / TW-23 autonomous-trainer capstone re-scope.** The original AI-first capstone framed this
  economics substrate as fuel for an autonomous EV-maximizing trainer. It is re-scoped: the
  substrate feeds a human-armed, priority-ranked, teacher-assisted trainer — the priority layer
  orders behaviors and suggestions, it is not a computed-EV action-picker.
- **Naming.** Legacy strategy prose says "Ore"; the code (`state_parser.COMMERCE_COMMODITIES`) and the
  world-model port record use **`Fuel Ore`** — the doc uses the code's name so a scored figure keys
  to a real stored commodity row.
- **No floor/regrowth/plague fields exist in code.** `state_parser`/`world_model` observe and
  persist only `amount` (trading units) and `pct` (% of max) plus the class code — there is no
  stored floor price, regrowth rate, or absolute stock-ceiling field. Every number in the
  Floor-price and Depletion sections is therefore a pure external hypothesis with no code backing
  yet; `distance-to-floor` is approximated by `pct` until a live floor is confirmed, and the
  `min(stock)` depletion input maps to the minimum of the legs' observed `amount` fields.

# Citations

- design history §16 — load-bearing flag: every specific number here is community/strategy-guide
  research, unverified against the live game.
- design history §16.2 — regrowth rate, route-longevity/depletion formula (H2), floor prices,
  plague-ceiling heuristic; Equipment-premium ordering (H3).
- `state_parser.py` (`parse_state`, `COMMERCE_COMMODITIES`, commodity-row and port-class-code parsing) —
  what the client actually observes per commodity.
- `world_model.py` (`write_from_state`, `write_port_only`, the per-sector `port` record) — the
  persisted profit database this substrate scores against.
- Reimagined from `knowledge/strategies/port-economics.md` (the frozen raw material), re-rooted in
  the reborn vision; consumers: [Trade Loops](/strategy/trade-loops.md),
  [Priority Engine](/engine/priority-engine.md); hazard/appetite link:
  [Exploration Policy](/strategy/exploration-policy.md); hold/turn inputs:
  [Game-Data Store](/engine/game-data-store.md); fair-value consumer:
  [Auto-Haggle](/engine/auto-haggle.md).
