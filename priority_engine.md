This document seeks to outline the different competing priorities of the TW2002 AI Client and how we balance these and in what order.

## Priority catalog

Each row is one strategic objective the client tracks or will track. **Goal type** is either **Boolean** (met / not met) or **Range** (progress toward a target). **Weight** is the design intent for ordering when a priority is unmet — higher numbers should dominate the list until satisfied. **Status** reflects what is in-tree today (2026-07-22), not aspiration alone.

| Priority | Goal type | Weight | Depends on | Status |
|---|---|---:|---|---|
| Identification of Turns & Credit Count | Boolean | 100 | — | **Implemented** — `state_parser.parse_state()` reads `turns_left`; credits use the strict `session.credits_snapshot()` path (WO-FA-SAFE), never a loose screen parse. `hud_seed.seed_hud_after_join()` sends `<I>` once when either value is still unknown after login. |
| Identification of type of ship flying | Boolean | 90 | turns/credits known | **Planned** — no current-ship introspection adapter exists yet (`game_data.py` module docstring). `ShipSpec` / `PlayerState` types exist for upgrade scoring but are not fed live. |
| Location of StarDock | Boolean | 85 | explore (when unknown) | **Implemented** — `world_model` landmark records + `explore.find_landmark_sectors()`. Shown in GOALS (`✓ StarDock @…`). Autopilot explore lane hunts via `explore.plan_find_stardock()`. |
| Identification of cost of other ships | Boolean | 80 | StarDock found | **Partial** — `introspector.py` parses StarDock shipyard listings; persistence lives in `game_data`. Not yet wired into `WorldSnapshot.ship_catalog`, so `_score_upgrade()` always skips on a live daemon. |
| Identification of cost of cargo hold upgrades | Boolean | 75 | StarDock found | **Partial** — `game_data.persist_cargo_hold_price()` / `get_cargo_hold_price()` store the live per-hold quote. GOALS shows `upgrade N/h` when known, `price?` when not. |
| Identification of cost of fighters | Boolean | 70 | StarDock found | **Planned** — fighter deploy/sell math exists (`fighter_toll_policy.py`) but StarDock fighter pricing is not a tracked goal yet. |
| Purchase of Additional Cargo Holds | Boolean | 65 | hold price known, credits sufficient, `travel_cost_rt` (Planned) | **Planned** — upgrade *decision* logic exists (`ship_upgrade_decision.py`); autopilot EXECUTE is navigation-only today (no purchase keystrokes). |
| Purchase of ship with Larger Cargo Holds | Boolean | 60 | ship catalog known, loop economics known, `travel_cost_rt` (Planned) | **Partial** — `_score_upgrade()` in `autopilot.py` scores a detour-to-StarDock upgrade by holds-only cr/turn EV, but live wiring lacks `current_ship`, `ship_catalog`, and `loop` inputs; travel feasibility is **one-way only** today (see § Execution travel cost). |
| Location any "Special Formation" ideal for Planet placement | Range | 55 | map exploration | **Partial** — `formations.py` detects topology (dead-ends, bubbles, one-ways, warp-sinks) and tags `genesis_candidates`. GOALS shows formation + genesis counts. No deploy action. |
| Place planet and use it to earn resources to sell | Boolean | 50 | genesis candidate chosen | **Planned** — genesis deploy is explicitly excluded from autopilot candidate kinds (safety whitelist). Doctrine lives in OKF (`knowledge/strategies/planet-colonization.md`). |
| Map 100% of Galaxy | Range (target 100%) | 45 | — | **Partial** — `explore.known_graph()` + map-fill BFS frontier (`explore.py`). GOALS shows `map Ns` (known sector count). No explicit %-of-galaxy scorer yet (galaxy size unknown until mapped). |
| Identification of Trade Loop Chains (longest chain) | Range | 40 | ports known | **Partial** — `chains.longest_profit_chain()` ranks closed cycles by hop count then cr/turn. `trade_adapter.build_trade_hops()` builds edges from world-model ports (FA4). GOALS + chain bubble show longest chain; `run_chain` candidate fires when player sits at chain start. |
| Identification of Sector-based Threats (mines or fighters) | Boolean | 35 | sector visited | **Partial** — `world_model` persists `threats.mines` / `threats.fighters` per sector; HUD METRICS aggregate counts. Threats do not yet gate autopilot candidate scoring. |

### Trade loop chains (detail)

The smallest chain is determined by two sectors side by side with warp each direction where each sector has a port we can trade at. Two side by side allows player to warp back and forth to trade. Three allows player to warp up and down the chain trading at each port along the way. Sectors 123 → 753 → 8293 then 8293 → 753 → 123; this would be example of a 3-link chain. The player trades two times each direction.

In code, a **TradeHop** is one directed port-to-port edge with positive margin; `longest_profit_chain()` searches for the best closed cycle (minimum two hops). Rank order: **hop count descending**, then **cr/turn descending** (`chains.py`, §16.2). The spectate CHAIN panel and bubble art visualize the current best chain; the autopilot `run_chain` candidate uses the same chain object but only emits a navigation keystroke when the ship is already at the normalized cycle start.

### Execution travel cost (distance to act)

The catalog rows above describe *what* to achieve. Executing a priority also costs **turns to reach the action and return to interrupted work**. "StarDock found" (boolean) is not the same as "affordable to leave this chain right now."

**Example (Max):** trading a profit chain and considering a bigger ship at StarDock. Before abandoning the chain you need: (1) which ship and its price, (2) how far StarDock is (hop count on the known graph), (3) a **round-trip** turn budget — warp out, buy at dock, warp **back to the chain you were working** — which is roughly **2× the one-way warp cost** (plus dock/menu turns not modeled yet). Only then can you compare stay-trading vs leave-for-upgrade.

#### One-way vs round-trip

| Leg | Meaning | Typical use |
|---|---|---|
| **One-way** | Known-graph hops from current sector to the action site (StarDock, chain start, frontier target) | Explore next hop; upgrade detour feasibility; each `TradeHop.turns` between two ports |
| **Round-trip (RT)** | Out to the action **plus** return to the sector/work you interrupted (e.g. chain cycle start) | Any detour that pauses an in-progress trade loop; upgrade pre-flight |

Do not treat a one-way path length as the full execution cost when the plan is "leave chain → StarDock → resume chain."

#### What exists in code today

| Concern | Status | Where |
|---|---|---|
| Shortest known-graph path (sector list, inclusive endpoints); hop count = `len(path) − 1` | **Implemented** | `explore.path_to_sector()`, `explore.known_graph()` |
| One-way route current → nearest StarDock | **Implemented** | `explore.plan_find_stardock()` → `WorldSnapshot.stardock_route` via `protocol._autopilot_snapshot_kwargs()` |
| Upgrade travel feasibility (one-way warps × current ship `turns_per_warp`) | **Implemented** (one-way only) | `autopilot._score_upgrade()`: `travel_turns = (len(stardock_route)−1) × current_ship.turns_per_warp`; gated with `payback + travel_turns ≤ productive` |
| Chain per-cycle turn wall | **Implemented** | `chains.ProfitChain.turns` (sum of hop `turns`); `trade_adapter` sets each hop's `turns` from inter-port path length |
| Productive turn budget (`turns_left − turn_reserve`) | **Implemented** | `state_parser` / `EconCaps`; used by `_score_chain()` and `_score_upgrade()` |
| Payback / hold economics (travel-agnostic) | **Implemented** | `ship_upgrade_decision.choose_upgrade()` — caller must layer travel on top (see its module docstring) |
| `run_chain` only when already at cycle start | **Implemented** | `_score_chain()` sets `next_sector` only when `chain.sectors[0] == snapshot.sector`; navigating *to* chain start is explicitly deferred follow-up (`autopilot.py` module docstring) |
| Return path StarDock → interrupted chain sector | **Implemented** (engine helper) | `priority_engine.compute_return_path()` / `path_to_sector()`; caller must supply graph + chain-start sector |
| RT-inclusive upgrade feasibility + stay-vs-leave EV | **Implemented** (engine) | `priority_engine.recommend_actions()` + `stay_vs_leave_upgrade()`; autopilot `_score_upgrade()` still one-way until wired |
| Dock / purchase menu turns in travel budget | **Planned** | EXECUTE is navigation-only; no keystroke budget for shipyard or hold-buy flows |
| GOALS line for RT hop estimate | **Planned** | GOALS shows StarDock sector and hold price hints; no `RT ~Nt` or pre-flight checklist glyph |

#### Pre-flight checklist (before abandoning a live chain for StarDock)

Intended gate before `upgrade` beats `run_chain` on the Layer 2 weigh list — **none of this is a single enforced checklist yet**; items 1–2 are partially satisfied in isolation today:

1. **Target ship + price known** — introspected catalog row with `cost > 0` (`ship_catalog`; live bridge **Planned**).
2. **One-way path to StarDock known** — `stardock_route` with `len > 1` or at-dock (`len == 1`); unknown route fail-closes (`upgrade: stardock route unknown`).
3. **Return path to chain start known** → compute **`travel_cost_rt`** ≈ `(hops_to_dock + hops_to_chain_start) × turns_per_warp` (same ship outbound; post-buy ship may differ — **Planned** refinement).
4. **Turn budget** — `travel_cost_rt + projected_payback ≤ productive turns` (extends today's one-way `payback + travel_turns` check).
5. **EV comparison** — credit chain profit forgone during RT travel: e.g. compare `chain.cr_per_turn × travel_cost_rt` (sunk window) against incremental gain after payback; **stay trading** if the chain wins (**Implemented** in `priority_engine.stay_vs_leave_upgrade()`; autopilot `_score_upgrade()` still one-way until wired).

#### Layer 1 (GOALS) vs Layer 2 (PRIORITIES)

**Layer 1 — informational prerequisites.** Surface what the operator (and future overlay) needs before a detour is sane: path length to StarDock, whether return-to-chain is pathable, and when pre-flight is incomplete. Today GOALS already shows StarDock sector, map size, chain hop count, and hold price — but **not** hop count, RT estimate, or a pre-flight-complete boolean. Planned boolean/range additions: `path_to_stardock_known`, `travel_cost_rt_computable`, `upgrade_preflight_complete` (all **Planned** as GOALS lines; not in `GoalsSnapshot` yet).

**Layer 2 — action EV.** Travel cost belongs in **feasibility gates first**, then **cross-kind EV**:

- **Feasibility (partial today):** `_score_upgrade()` already fail-closes on unknown route and one-way turn budget; should extend to **`travel_cost_rt`** before recommending leave-chain.
- **Cross-kind ranking (Planned):** when both `run_chain` and `upgrade` score, rank using RT-adjusted net EV — not raw `extra_cr_per_turn` vs `chain.cr_per_turn` as if the upgrade were free to reach. Unmet Layer 1 pre-flight booleans should **gate** the upgrade candidate (`⊘`) until the checklist passes (feeds the planned boolean-weight overlay).

`explore` baseline EV is intentionally tiny (`EXPLORE_BASELINE_EV`); its travel cost is one frontier hop per tick — different shape from a multi-hop StarDock detour + RT.

## Scoring, Weighting, and Ordering

Each priority should come with a score that grades the priority on whether it is met or how close to being met it is. This means each priority above also will have to have goal set. The type of goal should either be boolean or an expected value. So for example for Identification of Turns & Credit Count, it should have boolean yes/no if we've identified the values or not, but should have a really heavy weighting that ensures it is ordered to the top of the Priority list if not met. Some priorities would have a secondary priority. To accomplish one, we must work on or accomplish the other. To find the StarDock (primary priority) in most games you would have to explore the galaxy (secondary priority). To identify the cost of other ships, one must find the StarDock first, and to find the StarDock one must explore.

### Two layers (design vs. what ships today)

**Layer 1 — Goal status (informational).** The left-gutter **GOALS** section in spectate (`GoalsSnapshot` → `compose_primary_goals_lines()` in `spectate_layout.py`) renders each catalog item as a compact status line with glyphs: `✓` met, `·` in progress / unknown, `—` not applicable. This layer is **read-only context** for the operator — it does not pick the next action.

**Layer 2 — Action selection (EV weigh list).** The **PRIORITIES** section below GOALS shows the autopilot's ordered **effort candidates** for the current tick, ranked by **`priority_engine.recommend_actions()`** (RT travel + stay-vs-leave when chain/travel hints exist). Inputs are adapted from `status["autopilot_trace"]`, the panel chain object, and world-model StarDock/return paths (`spectate_layout.build_priority_engine_inputs()`). DECISIONS still shows trace detail from the same poll. Each line is ranked by expected value:

```
1 Trade chain 550
2 Upgrade 200
3 ⊘ Explore —
```

Sorting is highest `ev_cr_per_turn` first; unknown EV sorts last (`compose_priorities_lines()`). Gated/skipped candidates carry `⊘` and a gate reason in DECISIONS. Readable labels map `run_chain` → "Trade chain", `upgrade` → "Upgrade", `explore` → "Explore" (`PRIORITY_KIND_LABELS`).

These two layers are related but not identical: the catalog above describes *strategic prerequisites* (mostly boolean), while Layer 2 scores *immediate actions* (continuous cr/turn). The long-term design is to unify them — unmet high-weight boolean goals should boost or gate the EV of dependent actions — but that bridge is **not built yet**.

### Implemented action scorer (`autopilot.select()`)

Today, Layer 2 is implemented as a **continuous, stateless cost-benefit scorer** (`twclient/autopilot.py`):

1. **ASSESS** — fold live screen state (`parse_state` for sector/turns; strict `credits_snapshot` for balance) plus caller-supplied world-model inputs into one `WorldSnapshot`.
2. **SELECT** — score three candidate kinds every tick from scratch (no persisted pursuit):
   - `run_chain` — EV = `ProfitChain.cr_per_turn` when profitable hops exist and turn budget allows.
   - `upgrade` — EV = extra holds × margin/hold ÷ cycle wall-turns (holds-only delta; **one-way** travel feasibility checked separately — RT return + stay-vs-leave comparison **Planned**, see § Execution travel cost).
   - `explore` — fixed baseline EV (`EXPLORE_BASELINE_EV = 0.01`) so the client never idles when a frontier hop exists (§11).
3. Pick the highest EV; ties broken by sort order (`run_chain`, `upgrade`, `explore`).

Skipped candidates are fail-closed with explicit reasons (unknown credits, unknown StarDock route, empty hop graph, turn-reserve floor, etc.) — never guessed EV.

**EXECUTE** (live autopilot) is deliberately **navigation-only**: at most one sector-number keystroke per tick, gated on `main_command` classification. Trade execution, haggle, dock purchases, and planet deploy are separate drivers (`trade_driver.py`, future work).

### Planned boolean-weight overlay

The weight column in the catalog table (100 down to 35) is the intended **prerequisite ordering** once Layer 1 and Layer 2 merge:

- **Boolean unmet → sort key `(0, weight)`** so it always beats any action EV until satisfied.
- **Boolean met → sort key `(1, action_ev)`** so normal cr/turn ranking resumes.
- **Range goals → `(0, weight × (1 − progress))`** so partial credit keeps the item visible but below hard blockers.

Example dependency chain (secondary priorities):

```
turns/credits known
  └─ ship type known
       └─ StarDock located ──(requires explore when unknown)── map fill
            └─ ship prices known
            └─ hold upgrade price known
                 └─ purchase hold / buy bigger ship
                      └─ run trade chain (Layer 2 `run_chain`)
```

Explore (`explore` candidate) is the **shared secondary** for everything that requires unknown map data — StarDock hunt, port discovery, formation survey, and chain edge mining all reduce to frontier hops until the prerequisite boolean flips.

Threat identification (mines/fighters) is catalogued but **not yet** a scorer input; the intended behavior is to mark sectors unsafe and gate `run_chain` / explore paths through them unless toll math (`fighter_toll_policy.py`) says otherwise.

### Coach KB (separate system)

`data/coach/strategies.json` assigns each strategy card a `priority` integer for the TW-13 coaching/advice panel — a human-facing hint ordering, **not** the autopilot EV list. Do not conflate coach card priority with this engine's action ranking.

## TUI surfaces

| Panel | Region key | Contents | Source module |
|---|---|---|---|
| GOALS | left PRIORITIES gutter (top) | StarDock, map size, formations, longest chain, upgrade/hold price hints | `spectate_app._build_goals_snapshot()` |
| PRIORITIES (weigh list) | left PRIORITIES gutter (bottom) | Engine-ranked candidates 1…N (`⊘`, optional `RTNt`) | `compose_priorities_lines()` → `recommend_actions()` |
| DECISIONS | right column under HUD | Trace detail: chosen kind, rationales, gate reasons | `format_autopilot_trace_lines()` |
| CHAIN | viewport bubble row | Longest chain sector path | `compose_chain_bubbles()` |

When the terminal is too narrow for the left gutter (`cols < LEFT_GUTTER_MIN_COLS`), GOALS + weigh list fold into the idle DECISIONS pane instead.

## Module map

| Concern | Primary module(s) | Notes |
|---|---|---|
| **Priority engine (driver)** | **`priority_engine.py`** | **Implemented (2026-07-22)** — `recommend_actions()` ranks run_chain / upgrade / explore with **`travel_cost_rt`** + stay-vs-leave; pure logic + pytest |
| Goal status display | `spectate_layout.py` (`GoalsSnapshot`, `compose_primary_goals_lines`) | WO-P2-b |
| Action EV scoring (legacy per-kind) | `autopilot.py` (`assess`, `select`, `_score_*`) | Still navigation driver; upgrade path still **one-way** until wired to engine |
| Cross-seat trace schema | `autopilot.decision_to_trace()` | Feeds spectate + `tw status --json` |
| Map / StarDock / formations planning | `explore.py`, `formations.py` | Pure planners; `path_to_sector()` used by engine return-leg helper |
| Execution travel / RT budget | **`priority_engine.py`**, `explore.py`, `autopilot._score_upgrade()` | Engine: RT + stay-vs-leave **Implemented**; autopilot live select still one-way until thin wire |
| Trade loop discovery | `chains.py`, `trade_adapter.py` | Hops are caller-supplied / world-model derived |
| Ship upgrade decision | `ship_upgrade_decision.py` | Pure logic; needs live catalog bridge |
| StarDock price capture | `introspector.py`, `game_data.py` | Ship list + cargo-hold quote persistence |
| Threat persistence | `world_model.py`, `state_parser.py` | Per-sector `threats` on disk |
| Spectate layout | `spectate_layout.py`, `spectate_app.py` | WO-TUI-PRIORITIES-LEFT; PRIORITIES width = `HUD_GUTTER_W`; engine adapter in layout |

**`twclient/priority_engine.py` exists** — call `recommend_actions(...)` for RT-aware focus. Autopilot `select()` is **not yet** delegated to it (thin wire = open gap #9).

## Live daemon honest scope (2026-07-22)

What a real autopilot tick can actually choose today (`protocol._autopilot_snapshot_kwargs()`):

| Candidate | Wired? | Typical live outcome |
|---|---|---|
| `explore` | Yes | Default when frontier / StarDock route exists |
| `run_chain` | Yes (FA4) | Fires when `trade_adapter` yields hops AND ship at chain start |
| `upgrade` | No | Always skipped — `ship_catalog` / `current_ship` / `loop` not populated live |

Goal lines in GOALS still update from the world-model even when upgrade scoring is dormant (StarDock found, map count, chain hop count, hold price when captured).

**Priority engine** can already answer stay-vs-leave in unit tests / callers that pass economics + hop counts; live daemon does not call it yet.

## Open gaps (Planned)

1. **Ship identity bridge** — introspect current hull from `<I>` / shipyard screens into `WorldSnapshot.current_ship`.
2. **StarDock catalog bridge** — persist introspected ships into `ship_catalog` for `_score_upgrade()`.
3. **Loop economics bridge** — derive `LoopEconomics` from the active `ProfitChain` or pilot profile.
4. **Boolean-weight overlay** — unmet catalog booleans influence or gate Layer 2 ranking (merge Layers 1 and 2).
5. **Threat-aware routing** — fold `world_model.threats` into explore and chain path selection.
6. **Purchase / trade EXECUTE** — wire dock menus, haggle, and hold/ship buys (beyond navigation-only autopilot).
7. **Planet colonization** — genesis deploy as a gated, human-approved candidate kind (never silent auto-deploy).
8. **Live `travel_cost_rt` inputs** — populate return path StarDock → chain start on `WorldSnapshot`; feed engine from protocol snapshot kwargs.
9. **Wire `autopilot.select()` → `priority_engine.recommend_actions()`** — single driver for live navigation; spectate PRIORITIES already uses the engine (2026-07-22).
10. **GOALS pre-flight hints** — `RT ~Nt`, checklist glyph when chain active + StarDock known.