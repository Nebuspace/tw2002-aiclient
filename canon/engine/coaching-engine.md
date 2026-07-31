---
type: System
title: Coaching Engine — Contextual Advice (teaches, never acts)
description: The engine that reads live game state plus the world-model and surfaces the strategically-best option and its tradeoffs as a human-facing tip — it teaches options, it never silently plays a keystroke.
tags: [coaching, advice, human-facing, strategy-kb, trigger-map, teaches-never-acts, configurable-numbers, hypothesis, prescriptive]
timestamp: 2026-07-23T20:21:04Z
---

The coaching engine is the trainer's teacher-at-the-shoulder. On each settled screen it reads the
live classification and parsed state plus what the [world-model](/engine/world-model.md) knows, decides
which taught strategies are *relevant right now*, and renders the best option and its tradeoffs as a
short human-readable callout in the spectator's Decisions pane. That is the whole of its authority: it
**surfaces advice for the human to read**. It sends nothing, arms nothing, and picks no keystroke. It is
the human-facing counterpart to the fireable [rule/macro engine](/architecture/rule-macro-engine.md) —
where a rule is a guarded behavior the app may *play*, a coaching card is a sentence the human may
*read* — and it is distinct again from the [candidate miner](/engine/candidate-mining.md) and the
[AI teacher](/engine/ai-teacher.md), which propose inert *rule drafts* for approval. The coach proposes
neither a keystroke nor a rule; it proposes *understanding*. This concept is prescriptive: it specifies
the strategy knowledge base it teaches from, the game-state→strategy trigger map that decides relevance,
the advice renderer that never fires, and the configurable-numbers discipline that keeps every game
figure a hypothesis until proven.

# Schema

## The three-plus-one parts

| Part | What it is | Where it lives |
|---|---|---|
| **I1 — Strategy knowledge base** | The taught strategy *content*: encoded cards, one per play pattern, each with WHAT it is, the WHEN game-state trigger, tradeoffs/risks, and concrete steps + numbers. | Content authored in the `strategy/*` concepts; encoded as data and loaded by `coach_kb.py` (`StrategyCard`) from `data/coach/strategies.json`. |
| **I2 — Contextual trigger map** | The pure function from live game-state to the set of applicable strategy cards: docked→trade-eval, dead-end→colonize, toll→attack/pay/flee, depleting-source→rotate, explore→density-scan. | `infer_coach_triggers()` in `coach_engine.py`. Emits seven trigger ids the authored KB can fire; only `planet_management` stays authored-unreachable — see Code divergence. |
| **I3 — Contextual-advice engine** | The renderer that takes the triggered cards and composes the option + its tradeoffs as human-facing callouts — never a keystroke, never an armed behavior. | `compose_decisions_coach()` in `coach_engine.py`, consumed by `cockpit/decisions.py` in front of its honest-empty state. The pre-rebirth consumer was `spectate_app.py`, which the rebirth deleted; the reborn one is the cockpit's own DECISIONS composer. |
| **I4 — Configurable coaching parameters** | The numeric substrate the cards cite — every one a hypothesis carrying a verify-vs-live flag, never a hardcoded fact. | `CoachParam` loaded by `coach_kb.py` from `data/coach/params.json`; the convention itself is [game-data-store](/engine/game-data-store.md)'s. |

The load-bearing property that unifies all four: **the coaching engine is read-only with respect to the
game.** It reads state, it reads the KB, it writes text to a display pane. There is no path from a
coaching card to a live send. That is what makes it safe to run every cycle without any human arming —
teaching is not acting, so the human-arm-before-a-run invariant (which governs behaviors that *play*)
simply does not bind a surface that only *shows*.

## I1 — the strategy knowledge base

A `StrategyCard` is one taught play pattern reduced to a fixed shape so it can be rendered uniformly and
matched to context:

- **`id`** — stable identifier (`pair_trade_loop`, `toll_math`, `holds_first`, …).
- **`title`** / **`what`** — the human-readable name and the one-paragraph explanation of the pattern.
- **`when_trigger`** — the single game-state trigger id this card answers (`docked_at_port`,
  `loop_depleting`, `at_dead_end`, `toll_or_gate`, `planet_management`, `at_shipyard`,
  `chain_opportunity`, `exploring_frontier`). This is the join key the trigger map uses.
- **`tradeoffs`** — the risks and counter-considerations, so the card *teaches a decision*, not a verdict
  ("smaller faster loops can beat fatter slow ones"; "auto-engage is forbidden without an explicit
  operator call").
- **`steps`** — the concrete procedure, with numbers pulled from the parameter substrate, not baked into
  prose.
- **`okf_refs`** — cross-links back to the owning `strategy/*` concept(s) so a card is always traceable
  to its full spec.
- **`hypothesis_flags`** — the named unverified numbers this card leans on; a non-empty list is what earns
  a card its `(unverified)` badge when rendered.
- **`priority`** — an ordering hint (lower = surfaced first) used only to rank *which cards to show* when
  several trigger at once. It orders *advice on a screen*, never an action to play.

The cards span the whole strategic surface the reborn trainer teaches — trade (pair loops, longest
profit chains, route-longevity rotation), colonization (dead-end siting, planet-production compounding),
combat toll math (NPC-only), exploration (density-scan), and ship progression (holds-first) — one card
per pattern, each pointing at its authoritative `strategy/*` concept. The content half is authored
*there*; `coach_kb.py` is a pure loader and schema validator with no world-model dependency, so the
knowledge is data the operator can edit without touching code.

## I2 — the contextual trigger map

`infer_coach_triggers()` is the pure, fail-closed function from *what the screen and world-model show* to
*which strategy triggers apply*. It reads a small bag of live facts — the screen classification, the raw
prompt text, fighters aboard, whether a profitable chain is known, genesis/dead-end counts from the
world-model, the explore mode, and whether the current sector has a port — and emits the set of matching
`when_trigger` ids in a stable order. The mappings are the intuitive ones the map prescribes:

- `has_port` true, or a `port_trade` / `cim_report` classification → **`docked_at_port`** (trade
  evaluation);
- zero fighters aboard, or a `stardock`/`shipyard` prompt → **`at_shipyard`** (holds-first progression);
- a known chain of ≥2 hops → **`chain_opportunity`** (longest-profit-chain);
- intervention-derived `loop_depleting is True` → **`loop_depleting`** (route-longevity rotation);
- any genesis/dead-end formation nearby → **`at_dead_end`** (colonization siting);
- an active explore mode (non-`"off"` string) → **`exploring_frontier`** (density-scan);
- a toll/fighters prompt → **`toll_or_gate`** (fight/pay/reroute math).

"Fail-closed" is the safety property: an input the map does not understand simply omits that trigger — it
never guesses a strategy onto an unrecognized screen. This is the coaching-surface analogue of
stop-on-unknown: where the app-autopilot *halts* on a frame it cannot positively match, the coach
*stays silent* on context it cannot positively map. Neither improvises past the edge of what it knows.

## I3 — the contextual-advice engine

`compose_decisions_coach()` takes the triggered cards (via `kb.by_trigger()` for each trigger id),
de-duplicates them, sorts them by the card `priority` (then `id` for stability), and renders the top few
as short lines in the Decisions pane — each carrying an `(unverified)` suffix when the card leans on a
hypothesized number. It is deliberately a thin, honest renderer:

- **It never strips or invents card text.** What the human reads is the authored KB content, badged for
  verification status — not a paraphrase, not a fabricated recommendation.
- **When nothing triggers, it shows an honest empty state**, not a stub or a filler tip — the same
  placeholder the Decisions pane uses when there is genuinely no live trace and no coach match.
- **It yields the pane to live activity.** When a real autopilot trace or an active explore plan owns the
  Decisions pane, the coach steps back; coaching callouts fill the pane only when it would otherwise be
  idle. The coach is the teacher who speaks when there is a teachable moment and is quiet otherwise.

The one invariant that outranks every rendering detail: **the advice engine surfaces the option and its
tradeoffs; it does not fire the option.** There is no `send`, no macro arm, no control-lock acquisition
anywhere in this path — it composes strings for a read-only pane owned by [spectate](/surfaces/spectate-and-attach.md).
A coaching card that says "attack needs ~N fighters; reroute costs ~1 turn — your call" is teaching the
human a decision, never taking it.

## I4 — configurable coaching parameters

Every game number a card cites — port regrowth rate, the rotate-before-decay threshold, the plague-stock
warning proxy, the shield-to-fighters ratio hint, the buy-production unit-price ceiling, the adjacent-pair
turn estimate — is a `CoachParam` in `params.json`, and every one of them carries
`verified_vs_live: false` today. That flag is not decoration: it is the contract that the number is a
**hypothesis** drawn from community lore or a design guess, *not* a fact about this server, and must be
confirmed against live introspection before anything downstream treats it as truth. This is the
[game-data-store](/engine/game-data-store.md)'s portable-semantics discipline applied to strategy: the
coach authors the *shape* of a decision ("rotate when remaining trades drop below a threshold") and reads
the *value* from a configurable, verifiable parameter — never a hardcoded per-server constant. The
hypothesis discipline is itself a safety rule: a card that leans on an unverified number wears the
`(unverified)` badge so the human weighs the advice knowing the ground under it is provisional.

# Examples

```
Live context (spectate tick): docked at a Class-BBS port, a 2-hop profitable
chain is known, fighters aboard = 40, no explore running.

infer_coach_triggers(...) →  ["docked_at_port", "chain_opportunity"]

compose_decisions_coach(kb, triggers) renders (Decisions pane, read-only):

  Pair trade loops (unverified)
    Rank by cr/turn, not cr/trip; smaller/faster can beat fat/slow.
    Run until remaining-trades says rotate.
  Longest profit chain
    2-hop cycle, every hop positive; longer preferred, cr/turn breaks ties.

Nothing is sent. Nothing is armed. The human reads the options and decides.
The 'docked_at_port' card wears (unverified) because it leans on floor-price
and regrowth numbers still flagged verified_vs_live=false in params.json.
```

```
Live context: an unrecognized settled screen the classifier cannot anchor.

infer_coach_triggers(...) →  []   (fail-closed: no trigger guessed)
compose_decisions_coach(kb, []) →  honest empty-state placeholder

The coach stays silent on a frame it cannot map — the teaching-surface
analogue of the autopilot's stop-on-unknown. No advice is fabricated onto
a screen the trainer does not understand.
```

# Code divergence

**Status at tip (corrected 2026-07-30, `WO-COACH-ENGINE-DOC-SYNC` after #258–#263).** This section
previously described the engine as shipped "in `spectate_layout.py`, wired into `spectate_app.py`'s
Decisions pane." Both files were deleted by the `452d896` rebirth scaffold, so for a period this concept
described an implementation that did not exist. What is true at tip:

- **Restored:** `coach_kb.py` (I1/I4) and `coach_engine.py` (`infer_coach_triggers` I2 +
  `compose_decisions_coach` I3), ported as a severable kernel — not the surrounding spectate surface.
- **Consumer restored** (`WO-STATUS-CHAIN-SCALARS-COACH`, 2026-07-28). `cockpit/decisions.py` calls
  `infer_coach_triggers` + `compose_decisions_coach` in front of its two-line honest-empty state, so the
  DECISIONS pane renders authored cards whenever it would otherwise be idle. Three properties keep that
  inside the pane's never-raises contract: the KB load is attempted at most once per process and a failure
  is cached as "no KB" (degrading to the same empty state, never to per-frame file I/O); no prose is
  composed at the call site; and a live autopilot trace wins outright — the coach is consulted only when
  zero trace lines rendered, which is the yield rule I3 states above.
- **Trigger inputs at tip (after the coach/status wire tranche #258–#263).** Of `infer_coach_triggers`'
  nine parameters the DECISIONS consumer passes seven: `classification`, `fighters_aboard`, `chain` (via
  `chain_hops`/`chain_unit`), `has_port` (world-model merge, True-or-omit), `dead_end_count` (world-stats
  warp-degree-1 count), `explore_mode` (run intent from `explore_run_wire` while running+report), and
  `loop_depleting` (derived fail-closed from `status["intervention"]`, identity-true only). Top-level
  `status` also emits `credits` for GOALS; that key is not a coach-trigger input.
  **Still no status producer:** `genesis_count` — needs an honest `catalog_provider.genesis_candidates`
  reader (formations catalog); `at_dead_end` still fires from `dead_end_count` alone when that is > 0.
  **`prompt` is deliberately absent and must stay so.** `session/protocol.py:: _status_response` omits it
  because on a server that echoes at the password gate that line *is* the operator's credential
  (`canon/doctrine/secrets-and-credentials.md`, Code Divergence #1). Prompt-keyed arms — the
  `stardock`/`shipyard` half of `at_shipyard`, and `toll_or_gate` entirely — therefore cannot fire from the
  cockpit consumer and must not be "fixed" by re-adding the field. A structural pin keeps the consumer from
  ever asking for it. `at_shipyard` *does* fire from the cockpit when top-level `fighters_aboard == 0`
  (wired by `WO-STATUS-FIGHTERS-ABOARD`).
  **`docked_at_port` paths at tip:** `has_port is True` (primary idle path) or
  `classification in ("port_trade", "cim_report")`. `cim_report` is produced by `classify_screen` today;
  `port_trade` remains in the trigger map's anchor list but is not emitted by the classifier on the current
  fixture corpus — a classifier gap, not an engine one. Do not invent classifier capability in this concept.
- **Authored but unreachable:** `strategies.json` carries eight cards; the trigger map can produce seven
  ids. The sole authored-unreachable card is `planet_production` (`when_trigger=planet_management`) — it
  still needs an honest planet/genesis producer and must not be marked wired without one.
  `route_longevity` (`loop_depleting`) is reachable via the intervention-derived flag.

The coaching kernel as restored already matches the reborn frame:
it is a pure, fail-closed, read-only teacher that surfaces cards and never sends. The divergences are not
in the coach itself but in *sibling engines* that share its cr/turn strategy vocabulary while crossing the
line the coach never crosses — recorded here so this concept is not misread as blessing them (docs win: the
reborn target is that strategy *ranks and teaches*, it does not live-drive):

- **`autopilot.select()` is a per-cycle EV action-picker with a "never-idle" floor.** `autopilot.py`'s
  SELECT stage scores every candidate action by expected cr/turn *from scratch every tick* and picks one to
  execute, and it carries an `EXPLORE_BASELINE_EV = 0.01` explore floor whose stated purpose is that a
  lower-EV pursuit is never left idle — a computed EV can win the tick over whatever screen is showing. That
  is exactly the live per-cycle action-picker the reborn vision forbids: the strategic PRIORITY layer must
  *rank/order* which taught behaviors run, never let a computed EV override stop-on-unknown or drive a
  keystroke. The reborn correction retires the never-idle appetite and the `EXPLORE_BASELINE_EV`
  auto-driver justification; the runtime fix is owned by [app-autopilot-model](/architecture/app-autopilot-model.md)
  and [priority-engine](/engine/priority-engine.md), not by the coach.

- **`priority_engine.recommend_actions()` carries the same `explore_baseline_ev` and can be wired as a
  driver.** The priority engine's own module note describes it wiring `rank_action_priorities()` into
  `autopilot.select()`, and it too defaults an `explore_baseline_ev` (0.01, doubled for a pending pursuit).
  Used as a live per-tick selector this is the same divergence; the coach depends on none of it — it reads
  the world-model and the KB directly and renders text. The priority engine's *legitimate* reborn role is to
  order which taught behaviors/suggestions are offered, which is compatible with coaching; its
  action-picker wiring is the divergence.

- **Guarded chain execution is separate from coaching (ADR-003).**
  `TradeChainRunner` may execute one exact human-approved discovered
  fingerprint with per-send guards and depletion STOP; the coach still only
  teaches and ranks the option. It cannot approve, arm, select, or rotate a
  chain. The execution contract lives in
  [trade-loops](/strategy/trade-loops.md) and
  [app-autopilot-model](/architecture/app-autopilot-model.md).

- **The §22 / TW-23 capstone is re-scoped, not an AI-driver.** `autopilot.py` still frames itself as the
  "§22/§23 autonomous goal-orchestrator" whose EXECUTE stage sends navigation keystrokes. The reborn
  re-scope keeps the deterministic, taught-screen, human-armed, stop-on-unknown parts and retires the
  "orchestrator that drives itself" framing. Noted so the capstone's own docstring is read through the
  reborn lens; the coaching engine sits entirely on the teaching side of that re-scope and is unaffected by
  it.

None of the above touches the coaching engine's own safety: it has no send path, so even alongside a
diverging autopilot it can only ever teach.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot and escalation target; the app plays
  back only taught screens and STOPs on any unrecognized frame, re-validating the screen match every cycle;
  a taught behavior or background loop is human-armed before it runs; depletion/hazard guards STOP and
  escalate, never autonomously rotate; the AI is a retrospective, human-invoked teacher, never a live
  keystroke; live senders are `{app, human}` only; the strategic PRIORITY layer ranks/orders which taught
  behaviors run or which suggestions the human sees — it is not a live per-cycle action-picker that lets a
  computed EV win over an unrecognized screen; all game numbers are hypothesis/configurable, never hardcoded
  facts; docs win — code divergences are recorded, never silently conformed to.
- Operator rulings (2026-07-23): `strategy/` and `doctrine/` are first-class categories; the coaching KB
  content half lives in the `strategy/*` concepts and is loaded via `coach_kb.py`; the coverage meter is
  App-vs-Human live share with AI as a teaching-provenance axis (live AI share ≡ 0) — reinforcing that a
  teaching surface like the coach is definitionally not a live driver.
- Project canon cross-links: the `strategy/*` concepts (the card content this engine teaches from —
  [trade-loops](/strategy/trade-loops.md), [port-economics](/strategy/port-economics.md),
  [exploration-policy](/strategy/exploration-policy.md), [toll-and-defense](/strategy/toll-and-defense.md),
  [planet-colonization](/strategy/planet-colonization.md), [special-formations](/strategy/special-formations.md),
  [ship-progression](/strategy/ship-progression.md)); the [world-model](/engine/world-model.md) (the live
  facts the trigger map reads); [screen-understanding](/engine/screen-understanding.md) (the classification
  that anchors triggers); the [priority-engine](/engine/priority-engine.md) (the shared cr/turn ranking that
  orders behaviors — ranks, never a live action-picker); the [AI teacher](/engine/ai-teacher.md) and
  [candidate-mining](/engine/candidate-mining.md) (the sibling proposers of inert rule drafts, distinct from
  the coach which proposes understanding); [game-data-store](/engine/game-data-store.md) (the
  configurable-numbers / verify-vs-live convention I4 follows); [action-safety-guards](/doctrine/action-safety-guards.md)
  and [control-and-escalation](/architecture/control-and-escalation.md) (the stop/escalate contracts the
  coach's fail-closed silence mirrors).
- Disposition: NEW — the survey found no owning module for the coach dispatch/advice engine; it is distinct
  from rule *proposals* (the KB teaches human-facing options; rules are fireable behaviors).
- Code modules (plain text) — **at tip:** `coach_kb.py` (`StrategyCard` / `CoachParam` loader + schema
  validation, I1/I4), `coach_engine.py` (`infer_coach_triggers` = I2 trigger map, `compose_decisions_coach`
  = I3 advice renderer, plus the honest empty-state placeholder), `chain_units.py` (the hop/step arithmetic
  the trigger map consumes), `cockpit/decisions.py` (reborn DECISIONS consumer — fail-closed KB load,
  yield-to-live-trace, coach call when the pane would otherwise be idle). **Port-source only, deleted at
  the rebirth:** `spectate_layout.py` (original home of the two I2/I3 functions), `spectate_app.py`
  (pre-rebirth Decisions-pane wiring). Data: `data/coach/strategies.json` and `data/coach/params.json`
  (the KB content and hypothesis-flagged numeric substrate); and, for the recorded divergences,
  `autopilot.py` (per-cycle EV `select()` + `EXPLORE_BASELINE_EV`, §22/§23 orchestrator framing),
  `priority_engine.py` (`explore_baseline_ev`, `recommend_actions`), and `trade_driver.py` (`run_chain`
  autonomous chain runner).
