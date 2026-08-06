---
type: System
title: Ship Progression & Upgrade Decisions (holds-first)
description: When and to-what to upgrade holds and ships — a decision-support engine that returns recommendations and taught, human-approved behaviors, never an autonomous purchase that competes to execute.
tags: [strategy, ship-progression, holds-first, upgrade-decision, roi, alignment-gate, defense-floor, human-approved, recommend-only]
timestamp: 2026-07-23T20:21:14Z
---

Sooner or later every trader run reaches the same fork: the player has credits in hand and a
shipyard in reach, and the question is *should I spend now, and on what?* Bigger holds are the
single highest-leverage upgrade a trader can buy — more cargo per trip is more profit per turn — so
the temptation is always to buy the biggest ship and the most holds the moment the money exists.
That temptation is a trap, and a live-pilot run proved it: aggressive late-run upgrading turned ~100k
earned credits into capacity that could not amortize before the turn budget ran out, and the banked
total collapsed to a fraction of the peak. This concept is the discipline that keeps that from
happening again — a decision-support layer that answers *when* and *to-what* with an ROI-vs-turn-budget
gate, an alignment/rank filter, a per-turn (not raw) hold-throughput ranking, a loop-stock match, and
a defense floor.

Everything here is **recommendation and taught behavior, never an autonomous spend.** A dock purchase
is one of the trainer's irreversible, credit-spending actions; under the reborn framing it is *always*
a human-approved one-shot, never a candidate that a computed expected-value can slip past to execute on
its own. The decision engine ranks and explains; the coded auto-max-holds behavior detects the
opportunity and prepares the expansion; but the credit leaves the account only when the human says yes.
The engine's job is to make that yes (or no) an informed one — to hand the human a `{recommend,
rationale, payback}` verdict, not to press the buy key.

# Schema

## Holds-first economics (the H6 ordering)

The upgrade priority is a fixed ordering, not a per-run guess:

**holds > shields > fighters.**

- **Holds** are the throughput axis — the ceiling on cargo per trip, and cargo per trip is the
  numerator of every credits-per-turn figure. Rushing holds toward the current ship's maximum is the
  first-priority spend.
- **Shields** come second: they absorb damage before fighters or hull, and are rarely lost outright,
  so credits spent on shields tend to persist.
- **Fighters** come last as a *purchase* — they are consumable in combat and can often be harvested
  from planets rather than bought at rack price — but "last to buy" is **not** "zero." A ship must
  keep *some* defense (see the defense floor below); a maxed-holds ship with no fighters is a mugging
  waiting to happen.

### The ship-selection metric is per-turn, not per-hold

"Most holds" is *not* the same as "best ship on a turn budget." Ships differ in **turns-per-warp**:
a heavier hull can cost more turns per hop for its extra capacity, and those turns come straight out
of the run's finite budget. The real selection metric is throughput **per turn**:

```
holds_per_turn = (holds × margin_per_hold) / (turns_per_cycle × turns_per_warp)
```

At equal holds, a ship that burns more turns per warp ranks *lower*, because the same loop takes it
more turns to run. This is the metric the decision engine ranks eligible ships by — hold-throughput
per turn, sharing the loop's cycle length, penalized by the candidate ship's warp cost.

> **Verification status: HYPOTHESIS.** The illustrating figures from the originating live-pilot run —
> e.g. a heavy barge observed at ~6 turns/warp against a galleon-class hull at ~3, a higher-hold
> alignment-gated ship at ~255 holds — are *observed on one server, one run*, not portable facts.
> They are configurable inputs, read live per world (see the game-data store), never hardcoded here.
> Only the *shape* of the metric (per-turn, warp-penalized) is canonical; every number in it is
> introspected.

### Capacity must match loop-stock depth

A ship far bigger than the loop it feeds is wasted capital. A high-capacity ship hammers a small
loop's port stock to zero in a few cycles (ports regenerate slowly), so raw holds beyond what the
loop's stock can sustain buys nothing until the trade base grows. Capacity and loop-stock depth must
be **matched**: a ship whose holds exceed the loop's sustainable stock is not recommended until a
bigger loop or a multi-hop chain (the longest-profit-chain finder) can keep it fed. Growing holds and
growing the trade base are one coupled decision, not two independent ones.

## The ship-upgrade DECISION engine (WHEN + TO-WHAT)

The engine takes a catalog of candidate ships (each an introspected shipyard row), the player's
current state, and the economics of the loop they run, and returns a single `UpgradeDecision`:

```
UpgradeDecision { recommend: bool, ship, rationale: str, projected_payback: turns|None, flags }
```

It evaluates each candidate against **five gates**, every one a *refuse-closed* check — a candidate
must clear all five to be recommended, and the most informative refusal is surfaced when nothing
qualifies (so the human hears *why* a HOLD, not just "no"):

1. **Alignment / rank gate.** A better ship is frequently gated by standing, not just credits — "not
   commissioned to fly this ship" is a real block. An un-commissioned candidate is refused with an
   `alignment_rank` flag before any economics run. (Ship selection is credits **and** alignment/rank.)
2. **Loop-stock match.** If the candidate's holds exceed the loop's sustainable stock capacity, it is
   refused with a `needs_chains` flag — grow the trade base (chains) first.
3. **Defense floor.** On a hostile / PvP server, a candidate whose fighter capacity is below the
   configured defense floor is refused with a `defense_floor` flag — a zero-fighter hull is a
   StarDock-mugging risk. (The floor is a configurable policy value, not a game constant; its default
   is deliberately conservative.)
4. **Positive-delta gate.** A candidate that adds no holds over the current ship (or otherwise yields
   no positive credit-per-turn delta) has nothing to amortize and is refused — no upgrade, no
   recommendation.
5. **ROI-vs-turn-budget gate.** The engine computes `projected_payback` — the turns needed to amortize
   the upgrade's cost (ship price plus the credits to fill the extra holds) out of the *extra*
   credits-per-turn the bigger ship earns. If that payback exceeds the player's **remaining productive
   turns** (turns left minus a safety reserve), the verdict is HOLD with a `roi_vs_budget` flag: the
   capacity cannot pay for itself in the turns that remain. *Don't buy capacity you can't run.*

A candidate that clears all five is recommended, and among all recommended candidates the engine picks
the highest **holds-per-turn** — the per-turn throughput metric above, so the winner is the best
turn-efficient upgrade the budget can actually amortize, not merely the one with the most holds.

The engine is **pure logic**: it reads introspected numbers and player state and returns a verdict. It
sends no keystroke, spends no credit, and holds no control lock. Its output is advice for the human and
an input to the priority ranking — nothing more.

## Coded auto-max-holds (the taught behavior)

Separate from the *decision* engine is the *behavior* the operator most wanted: **coded auto-max-holds.**
The intent is that the app auto-detects the earliest shipyard opportunity — StarDock reached, capital
sufficient — and expands the current ship's holds toward that ship's maximum as credits allow, without
the human having to hand-order it every time. It is a **taught, deterministic behavior**: a guarded
rule (StarDock-landmark screen recognized → hold-expansion macro) that plays only on the screens it was
taught, re-validating the screen match each tick and stopping the instant the frame is unrecognized.

Two invariants bound it, and neither is negotiable:

- **Human-armed before it can run.** Like every taught behavior and background loop, auto-max-holds is
  armed by the human before it may fire — it does not self-enable because the conditions happen to line
  up.
- **The purchase itself is a human-approved one-shot.** Detecting the opportunity and preparing the
  expansion is deterministic and coded; committing the credits is a confirm-gated action the human
  approves. Auto-max-holds automates the *recognition and the setup*, not the *spend*. Even fully
  armed, the actual buy remains an approve/reject moment, never one keystroke to live money.

This is holds-first made mechanical — the trainer stops making the human re-issue the same
"grow my holds" order at every shipyard — without turning a credit-spending irreversible into an
autonomous act.

## Reborn framing — why an upgrade is never a competing candidate

The load-bearing distinction: a ship upgrade is a **recommendation the human acts on**, or a
**human-armed taught behavior whose spend is human-approved** — it is *never* an autonomous candidate
that a per-cycle expected-value picker can select and execute on its own. The strategic priority layer
may **rank** an upgrade recommendation against the other things the human could do next, and may
surface it more or less prominently — but ranking orders *suggestions*; it does not let a computed EV
win the right to press the buy key past an unrecognized screen or without the human's yes. Depletion
and hazard conditions (a small loop hammered to zero, a hostile sector) are **STOP-and-escalate**
guards, not triggers for the app to autonomously rotate to a different ship or loop. The engine
informs; the human decides; a guard can always STOP instead of acting.

# Examples

**A late-run HOLD.** The player has ~100k credits and a big ship is affordable and commissioned, but
only ~180 productive turns remain. The engine computes the upgrade's payback at, say, ~260 turns and
returns `recommend: false`, rationale "payback 260 turns > remaining productive 180 — HOLD
(ROI-vs-turn-budget)". The human keeps the money liquid instead of sinking it into capacity that would
never amortize — exactly the mistake the originating live run made *before* this gate existed.

**A commissioned block.** The catalog's best ship by raw holds is alignment-gated and the player's
standing doesn't clear it. The engine refuses that candidate with an `alignment_rank` flag and, if a
smaller commissioned ship clears every gate, recommends *that* one instead — the affordable-in-credits
but unaffordable-in-standing ship is never suggested as if it were buyable.

**Warp-cost flips the ranking.** Two ships are both commissioned and both loop-stock-compatible; one
has more holds but a higher turns-per-warp. On raw holds the bigger ship "wins," but on holds-per-turn
the lighter, cheaper-to-move ship scores higher for the loop in question, and the engine recommends it.
"Most holds" lost to "most holds *per turn*."

**Defense floor on a hostile server.** A maxed-holds hull is available with zero fighters on a PvP
server. The engine refuses it with a `defense_floor` flag rather than recommend a mugging risk — the
holds-first ordering never means holds-*only*.

**Auto-max-holds, armed but still gated.** The human arms auto-max-holds. On the next StarDock visit
with sufficient capital, the app recognizes the shipyard screen and prepares the hold expansion — then
surfaces the confirm gate. The human approves, and only then do the credits leave. Had the shipyard
screen been anything the behavior wasn't taught, the app would have stopped and handed over the
keyboard instead.

# Code divergence

DOCS WIN: the following are places where the current implementation diverges from the reborn target
this concept prescribes. The prescription stands; these are recorded, not silently conformed to.

- **The decision engine is built; its live inputs are not yet wired.** `ship_upgrade_decision.py`
  implements the five gates, the holds-per-turn metric, the payback computation, and the
  best-of-eligible chooser as pure logic — every input (`ShipSpec`, `LoopEconomics`, `PlayerState`) is
  today a mockable stand-in. The bridge from the introspected per-world game-data store to `ShipSpec`
  exists (`game_data.ship_row_to_spec`), but no live flow yet reads the current loop economics, player
  turns/alignment/holds, and a captured shipyard catalog and calls `choose_upgrade`. The engine is
  correct in isolation; the wiring that feeds it real numbers is the missing link.

- **Coded auto-max-holds (TW-22) — recognition + toward-max qty LIVE; catalog ship
  max still optional.** App-armed Cargo Hold Upgrade (`_autonomy_auto_fire` +
  `stardock_hold_plan.plan_from_status(..., auto_max=True)`) expands qty toward
  empty-hold capacity as credits allow (after cash floor), reusing the existing
  one-pass driver. Manual `H` / confirm offers stay qty=1. Per-ship `max_holds`
  from Layer-B catalog is not yet required — HUD empty-holds already is room to
  the ship's current max. Live StarDock capture (game_data) feeds the hold price.

## One-pass StarDock hold driver (tip)

The execute path for a human-approved (or App-armed `C)argo Hold Upgrade·ON`) hold buy is
**not** a multi-hop navigator and **not** a trade-chain runner. Tip modules:

| Module | Role |
|---|---|
| `tw2002_aiclient/stardock_hold_plan.py` | Pure evidence → `StardockHoldPlan` (world_id, fingerprint, sector, empty, unit price, credits, qty). Incomplete/hostile fields → `None` (fail-closed). Parses quote + P-QTY range from screen text. |
| `tw2002_aiclient/stardock_hold_driver.py` | `run_hold_purchase(session, plan, should_abort=, is_armed=)` — **one send**: the planned qty string. Expects quote (+ qty prompt) already on screen. |

**Safety pins (do not "simplify" away):**

- Never pays fighter tolls; never calls explore / trade_chain.
- Refuses unknown P-QTY ranges (`unknown_qty_range`) and qty outside the stated range.
- Refuses when on-screen unit price ≠ plan (`hold_price_mismatch`).
- Re-checks `should_abort` / `is_armed` before send; Mode-leave halt covers this runner
  (`stardock_hold_stop` — see [mode-line](/surfaces/mode-line-and-teach-controls.md)).
- Display/session sends only — sibling of the guarded trade one-pass shape, money-path adjacent.

*(Honesty pass `AUDIT-CANON-DRAFT-STARDOCK-HOLD-DRIVER-COVERAGE`, 2026-08-04.)*

- **Archived autopilot per-cycle EV picker — do-not-revive.** Pre-rebirth `twclient/autopilot.py`
  selected each tick's action by expected-value-per-turn across candidates (an upgrade could compete
  to execute). That module is **archive-only**. Under the reborn framing an upgrade is a
  recommend-only / human-confirmed spend, never an unsupervised EV winner. Archive
  `EXPLORE_BASELINE_EV` "no idle" keep-driving is likewise do-not-revive; tip explore floor is
  FOCUS suggestion-only ([app-autopilot-model](/architecture/app-autopilot-model.md)).

- **Guarded discovered-chain framing resolved by ADR-003.** `TradeChainRunner`
  now requires an exact human-confirmed fingerprint, daemon re-resolution, and
  one-pass bound while retaining the driver's per-send guards. Ship progression
  may inform the economics but cannot approve, arm, launch, or rotate the run.

- **The §22.4 "full-autopilot capstone" is re-scoped by the reborn vision.** The v2 design history
  frames the end-state as *start the client → it goes autopilot → autonomously double starting credits*
  by orchestrating explore + chain-find + auto-max-holds + loop-trade + auto-haggle, all
  trainer-driven. Ship-progression's auto-max-holds (§22.3) was authored as a component of that
  autonomous capstone. Under the reborn constraints the capstone's *autonomous self-flying* goal is
  retired: the same components survive as human-armed taught behaviors and human-approved spends, ranked
  by the priority layer, each stopping on the unrecognized screen — not as an unsupervised
  credit-doubling autopilot. Recorded so the origin is clear and the re-scope is explicit.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot; the app plays back only taught
  screens and STOPs on the unrecognized, re-validating every cycle; a taught behavior or background
  loop is human-armed before it runs; depletion and hazard are STOP-and-escalate guards, never
  autonomous rotation; the priority layer ranks and orders taught behaviors and suggestions but never
  overrides stop-on-unknown; all game numbers are hypothesis / configurable, never hardcoded facts.
- Internal design history — the holds-first upgrade ordering (holds > shields > fighters); the five
  ship-progression learnings from a live-pilot run (ROI is turn-budget-dependent; better ships are
  alignment/rank-gated; warp-cost varies per ship so "most holds" ≠ best; a big ship outstrips a small
  loop's stock; defense matters — keep some fighters); the coded auto-max-holds behavior the operator
  hand-ordered repeatedly; and the full-autopilot capstone the reborn vision re-scopes.
- Code modules — `ship_upgrade_decision.py` (the pure five-gate decision engine: alignment/rank,
  loop-stock, defense-floor, positive-delta, and ROI-vs-turn-budget gates; the holds-per-turn
  throughput metric; the payback computation; and the best-of-eligible chooser returning `{recommend,
  ship, rationale, projected_payback, flags}`), `game_data.py` (the introspected per-world ship rows
  and the `ship_row_to_spec` bridge that feeds the engine), `chains.py` (the longest-profit-chain
  finder whose loop economics the loop-stock match and per-turn metric depend on), archive-only
  `twclient/autopilot.py` (do-not-revive EV picker / `EXPLORE_BASELINE_EV` auto-driver),
  `trade_driver.py` (arm-gated chain runner), and tip hold-buy execute
  — `stardock_hold_plan.py` / `stardock_hold_driver.py` (`run_hold_purchase` one-pass; refuse unknown
  qty range / price mismatch; never toll-pay or trade_chain).
- Cross-cutting invariants and consumers — [game-data-store](/engine/game-data-store.md) (the
  introspected ship stat rows and per-hold price this engine reads, never hardcodes),
  [priority-engine](/engine/priority-engine.md) (which *ranks* an upgrade recommendation among
  suggestions — ordering, never a live action-picker that lets EV override stop-on-unknown),
  [trade-loops](/strategy/trade-loops.md) (the loop-stock depth an upgrade's capacity must match),
  [action-safety-guards](/doctrine/action-safety-guards.md) (the human-approval confirm gate every
  dock purchase passes through), [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md)
  (`C)argo Hold Upgrade·ON` + Mode-leave `stardock_hold_stop`), and
  [menu-map-and-introspection](/engine/menu-map-and-introspection.md)
  (the read-only shipyard navigation that captures the catalog and the StarDock landmark auto-max-holds
  keys off).
