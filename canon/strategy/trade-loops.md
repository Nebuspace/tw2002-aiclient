---
type: System
title: Trade Loops & Chains — Profit-per-Turn Play
description: How the trainer defines, ranks, and runs trade loops — pair loops and multi-hop chains scored by credits-per-turn — as taught, human-approved repeating macros whose depletion guards STOP and hand the keyboard to the operator rather than rotate on their own.
tags: [strategy, trading, trade-loops, profit-chains, credits-per-turn, taught-macro, depletion-guard, stop-on-unknown, prescriptive]
timestamp: 2026-07-23T20:20:02Z
---

A trade loop is the base unit of income in TW2002: a repeating cycle across ports whose commodity
postures are complementary — one port sells what the next one buys — worked over and over so that
the travel turns amortize across every future rotation. This concept defines the loop and its
generalization, the multi-hop **profit chain**; specifies the profit-per-**turn** scorer and the
chain execute-floor thresholds; and fixes the reborn contract for how loops actually run. That
contract is the whole point: a loop is a **taught, human-armed, repeating macro**, not an appetite
the app satisfies on its own. The priority layer RANKS which loop is worth offering or running; it
never lets a computed profit win over an unrecognized screen. When a loop depletes, the guard
STOPS and escalates to the operator — it does not autonomously rotate to a fresh loop. Everything
here is prescriptive spec feeding rule-guards, priority scoring, and operator coaching; where the
current code still carries a pre-reborn autonomous-driver shape, that divergence is recorded below,
never silently conformed to.

# Schema

## The unit edges — TradeHop and ProfitChain

- **`TradeHop`** — one directed, positive-margin port→port edge: `{frm, to, commodity, margin,
  turns}`. A hop is valid only when `frm`'s port *sells* the commodity (the player buys there) AND
  `to`'s port *buys* the same commodity (the player sells there). Two ports both selling, or both
  buying, the same commodity are NOT a compatible pair — no hop, fail-closed. `margin > 0` and
  `turns > 0` are hard filters: a non-positive-margin or zero-turn edge is never a hop
  (`chains.TradeHop`, `trade_adapter.build_trade_hops`).
- **Pair loop** — the smallest chain: two adjacent ports connected by a two-way warp, each buying
  what the other sells, so the cycle is buy → warp → sell/buy → warp → sell. A port co-located with
  the operator's own planet can act as the second leg, removing a full travel leg from the cycle.
- **`ProfitChain`** — the best closed cycle discovered over the known TradeHop edges: an ordered
  ring of sectors (`first == last`) with its hops, carrying `overall_profit`, `turns`,
  `cr_per_turn`, and `cr_per_execution` (`chains.ProfitChain`).

## Ranking — hop-count first, then credits-per-turn

Candidate chains rank by **hop-count descending, then credits-per-turn descending**
(`chains.rank_chains`: `key = (len(hops), cr_per_turn), reverse=True`). A longer chain that keeps
the ship productive across more distinct legs is preferred, and among equal-length chains the one
that earns more per turn wins. This ordering feeds the priority layer as a *ranking* input for
which taught loop to offer or prioritize — it is not a live per-cycle action-picker.

## The profit-per-TURN scorer [H1]

Score a loop by **credits-per-turn, not credits-per-trip.** A loop with a smaller net profit but
fewer turns per cycle out-earns a bigger, slower loop: a hypothetical 400 cr over 5 turns
(80 cr/turn) beats 500 cr over 10 turns (50 cr/turn). Turns-per-cycle is a first-class ranking input
alongside net credits. Loop *shape* sets the turn floor — an adjacent pair (one warp each way) is
the cheapest shape by hop-count; a port-plus-co-located-planet shape removes a leg; and the actual
turn cost of any warp depends on the ship flown (see [Ship Progression & Upgrades](/strategy/ship-progression.md)
for turns-per-warp by ship).

- **[H1 hypothesis]** The credits-per-turn ranking rule and the illustrative 400/5-vs-500/10 figures
  are a modeling choice, not a measured game constant. *Verification: UNVERIFIED — the ranking rule
  is prescriptive; the specific credit/turn numbers are illustrative only and must be validated
  against live play.*

## Chain execute-floor thresholds — rule-guard inputs

These are code constants (`priority_engine.py`), not game numbers — they gate which taught macros
are *offerable* and how the earn-vs-search band is chosen:

- **`MIN_CHAIN_LINKS_TO_EXECUTE = 2`** — a chain shorter than two links (a single hop, or empty) is
  discovery-only: it is never offered as an executable earn macro; below it the layer prefers to
  keep searching/exploring.
- **`CHAIN_LINKS_PREFER_SEARCH_BELOW = 2`** (defined as `= MIN_CHAIN_LINKS_TO_EXECUTE`) — the
  earn-vs-search band boundary: at or above it, *earning* on the known chain is preferred over
  hunting a longer one; below it, exploration stays the preferred secondary candidate.
- **`MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE = 4`** — a hull/ship upgrade is not prioritized until the best
  known chain is at least four links; at 2–3 links, capital is steered to holds and defense first
  (see [Ship Progression & Upgrades](/strategy/ship-progression.md)).

These thresholds are **inputs to the priority ranking and rule-guards** — they decide what the
layer offers and how it orders candidates. They do NOT authorize the app to drive over an
unrecognized screen; the stop-on-unknown invariant is prior to and independent of any threshold.

## The pair-trade macro — `scope: repeating`, posture-matched, depletion-guarded

A worked loop is a **taught, human-armed, repeating macro** (`scope: repeating` in the
[Guarded Rule–Macro Engine](/architecture/rule-macro-engine.md)):

- **Screen-guard = port-posture match.** The macro fires only when the current screen is the
  recognized port/trade screen AND the port's live commodity posture matches what the loop expects
  (the `selling`/`buying` status per commodity — `trade_adapter`'s perspective rule: `frm` sells,
  `to` buys, never inverted). An unrecognized screen — anything the guard does not positively match
  — STOPS the run and hands the keyboard to the operator, re-validated at EVERY cycle, not just at
  arm time.
- **Human-armed before it can run.** A repeating trade loop does not start earning on its own. The
  operator arms it; only then may the app play the taught cycle.
- **Depletion → STOP-guard + escalate, never autonomous rotation.** A loop is not infinite: a
  port's tradeable stock depletes as it is worked, and margin shrinks toward the floor. When a
  depletion signal fires (a target commodity absent from the trade cascade, or realized margin
  falling below the floor), the guard STOPS the run and escalates to the operator with a typed
  reason — it does NOT silently rotate to a fresh loop or keep burning turns for shrinking margin.
  Rotating to a replacement is an operator decision (informed by the coaching layer), never an
  autonomous act. The **runtime owner** of that STOP — the run-loop that re-validates each screen,
  halts on the unknown, and holds the keyboard for the operator — is the
  [APP Autopilot Model](/architecture/app-autopilot-model.md); this concept specifies WHAT the loop
  is and WHEN it must stop, that concept owns the mechanism.

The numeric substrate the depletion predictor and the price/spread estimate depend on — floor
prices, the stock-vs-price curve, and the remaining-trades model — lives in
[Port Economics](/strategy/port-economics.md); every number there is `[hypothesis]`/UNVERIFIED and
configurable.

## The longest-profit-chain finder (TW-21) — cockpit centerpiece

The chain finder (`chains.find_profit_chains` / `longest_profit_chain`) searches the known
TradeHop edges for the best closed cycles and surfaces each with **three metrics**:

- **overall profit** (`overall_profit` / `cr_per_execution`) — credits per full chain execution,
- **average credits-per-turn** (`cr_per_turn`) — the profit-per-turn ranking metric,
- **credits per chain-execution** — the per-loop yield.

The finder is a **world-model consumer that surfaces to the operator** — a suggestion and a cockpit
centerpiece (the discovered chain rendered as a coach callout / library row), not an executor. It
reads persisted port records via `trade_adapter.build_trade_hops` over the
[World Model](/engine/world-model.md); it sends nothing and drives nothing. The
[Priority Engine](/engine/priority-engine.md) ranks the finder's output to decide which chain is
worth offering; the operator decides whether to arm it.

# Examples

```
Pair loop (smallest chain, 2 links):
  Sector A port SELLS Equipment, BUYS Fuel Ore
  Sector B port SELLS Fuel Ore,  BUYS Equipment
  A —warp→ B —warp→ A, one two-way warp each leg.
  Buy Equipment at A → sell at B, buy Fuel Ore at B → sell at A. Repeat.
  Cheapest shape by hop-count; actual turn cost depends on the ship's turns-per-warp.

Profit-per-turn ranking [H1, illustrative]:
  Loop P: +400 cr / 5 turns  = 80 cr/turn   ← preferred
  Loop Q: +500 cr / 10 turns = 50 cr/turn
  Q earns more per trip but P earns more per turn — P wins on the scorer.

Execute-floor bands (rule-guard inputs, priority_engine.py):
  best chain links   layer behavior
  0–1                discovery-only — not offered as an earn macro; prefer search/explore
  2–3                earn on the known chain; ship upgrade NOT yet prioritized
  ≥4                 earn; ship/hull upgrade becomes an eligible prioritized recommendation

Depletion STOP (never autonomous rotation):
  target commodity absent from the trade cascade, OR realized margin < floor
    → guard STOPS the run, escalates to the operator with a typed reason
    → operator (informed by coaching) decides whether to rotate to a fresh loop
```

# Code divergence

The reborn contract above is the target. The current code still carries a pre-reborn
autonomous-driver shape in three places; these are recorded, not conformed to:

- **`autopilot.py` per-cycle EV picker + `EXPLORE_BASELINE_EV` "never idle."** The autopilot's
  `SELECT` step is a continuous per-tick cost-benefit scorer that picks the highest expected-value
  candidate from scratch every cycle, with no committed-pursuit state — a lower-EV pursuit is
  "naturally abandoned" the instant a higher-EV one out-scores it. Combined with
  `EXPLORE_BASELINE_EV = 0.01` (a deliberately-nonzero explore floor under §11 "no idle") this is
  an autonomous action-picker with a never-idle appetite — exactly the shape the reborn vision
  retires. Reborn target: the priority layer RANKS/ORDERS taught behaviors; it does not let a
  computed EV win over an unrecognized screen, and explore is a taught, budgeted, human-armed
  behavior, not a keep-driving baseline. A continuous EV re-pick across chains is also *de-facto
  autonomous rotation* — the reborn depletion contract forbids it (rotation is an operator
  decision).
- **`trade_driver.run_chain()` autonomous chain runner.** `run_chain()` drives a whole discovered
  `ProfitChain` end-to-end in one synchronous call — navigate → dock → buy → navigate → dock → sell
  → repeat across every hop — under `MODE_AUTO_LOOP`. It is well-gated (a REQUIRED, fail-closed
  `should_abort` and `is_armed` checked at every send choke point, a fresh-render gate before each
  send, PALADIN letter-allowlist, no counter/haggle), and it HOLDs cleanly on any unexpected screen.
  But it is still an autonomous multi-hop drive, not the reborn per-cycle "re-validate the
  screen-match every tick, stop on the first unrecognized frame, hand the keyboard back" run-loop
  owned by the [APP Autopilot Model](/architecture/app-autopilot-model.md). The reborn shape moves
  the drive under that per-cycle-revalidating owner.
- **Depletion as an internal `ChainHold`, not an operator escalation.** `trade_driver` detects
  depletion (`ChainHold("depleted:...")`) and margin-floor breaches
  (`realized_margin_below_floor:...`) and *aborts the chain internally*, after which the autopilot's
  next tick simply re-picks the next-best candidate — the current code path is closer to silent
  rotation than to STOP-and-hand-to-the-operator. Reborn target: depletion fires a typed escalation
  that STOPS and surfaces to the operator, who decides whether to rotate.
- **§22 / TW-23 autonomous-trainer capstone re-scope.** The original §22/TW-23 "autonomous trainer"
  epic assumed the app keeps driving and selecting actions on its own. Under the reborn vision that
  capstone is re-scoped: the never-idle keep-driving appetite is retired; the app plays only taught,
  human-armed macros and stops on the unknown. This concept's ranking/scoring content survives the
  re-scope; the autonomous-execution framing does not.

# Citations

- Design history §16.2 — profit-per-turn scoring; adjacent-pair vs planet-side loop shape.
- Design history §8 — live-play finding that a depleting loop should trigger a *replacement*
  decision rather than be abandoned outright (reborn: that decision is the operator's, not an
  autonomous rotation).
- Code module `chains.py` — `TradeHop`, `ProfitChain`, `find_profit_chains`, `rank_chains`
  (hop-count desc then cr/turn desc), the three-metric shape, `longest_profit_chain`.
- Code module `trade_adapter.py` — world-model port records → `TradeHop` edges; the buy-at-`frm`
  (port selling) / sell-at-`to` (port buying) perspective rule; the amount-floor phantom-leg gate;
  the UNVERIFIED floor-price / linear stock-price model deferred to Port Economics.
- Code module `trade_driver.py` — `run_chain()` end-to-end drive, `should_abort`/`is_armed` gates,
  fresh-render + PALADIN allowlist, `ChainHold("depleted:...")` / `realized_margin_below_floor`.
- Code module `priority_engine.py` — `MIN_CHAIN_LINKS_TO_EXECUTE=2`,
  `CHAIN_LINKS_PREFER_SEARCH_BELOW=2`, `MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE=4` and the earn-vs-search
  band.
- Code module `autopilot.py` — the per-tick continuous-EV `SELECT` scorer and
  `EXPLORE_BASELINE_EV = 0.01` (recorded as a reborn divergence).
- Reimagined from `knowledge/strategies/pair-trade-loops.md` (raw material; re-rooted in the reborn
  vision — the priority layer ranks/orders, it does not pick a live action over an unknown screen).
