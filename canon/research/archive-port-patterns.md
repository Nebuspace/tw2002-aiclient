---
type: Reference
title: Archive Port Patterns
description: >
  Distilled algorithmic and structural patterns from the pre-rebirth tw2002-aiclient archive
  (archive/pre-rebirth-2026-07-23/) that are directly useful for the reborn greenfield build.
  Extracted as portable prose and pseudocode — NOT copied module text. Each pattern is labelled
  with the reborn concept it feeds and any necessary reframing away from the old AI-first model.
tags: [research, archive, patterns, reference, porting, algorithms]
timestamp: 2026-07-25T21:47:34Z
---

# Archive Port Patterns

This document mines the pre-rebirth implementation at
`archive/pre-rebirth-2026-07-23/code/twclient/` for portable algorithmic patterns, data models,
and battle-tested heuristics. These are **reference material for the greenfield build** — the
archive is proof the patterns are sound, not code to be restored.

**Reborn framing throughout.** Any pattern that previously framed the _app_ as an autonomous AI
driver is rewritten: the reborn app only plays taught screens under human supervision. See the
Negative Patterns section for explicit do-not-port items.

**Relationship to other research.** Prompt/screen *shape* patterns from ClassicTW/TWGS research live in
[TW2002 Screen Patterns](/research/tw2002-screen-patterns.md) (P-BLOCK, P-QTY, P-SETTLE-LINE, …).
Owning prescribe-and-classify prose is [Screen Understanding](/engine/screen-understanding.md).
This document covers the _algorithms and data structures_ from the pre-rebirth archive that consume
those anchors — complementary, not duplicate.

---

## Schema Catalog

| ID | Pattern | Archive Module | Reborn Concept | Priority |
|----|---------|---------------|----------------|----------|
| AP-01 | Two-tier classify (gate/content) with stale-scrollback discipline | `classify.py` | [Screen Understanding](/engine/screen-understanding.md) | P0 |
| AP-02 | `send_and_confirm` settle protocol | `settle.py` | [Settle Detection](/architecture/settle-detection.md) | P0 |
| AP-03 | Reactive login automaton — nuisance table + stagnant-rounds | `login.py` | [Login Automaton](/architecture/login-automaton.md) | P0 |
| AP-04 | Skill record / replay / play with halt-on-divergence | `skills.py` | [Macros](/engine/macros.md) | P0 |
| AP-05 | Deterministic haggle — evidence-backed price, desync fallback | `haggle.py` | [Auto-Haggle](/engine/auto-haggle.md) | P0 |
| AP-06 | Per-sector world-model store (fcntl lock, atomic rename) | `world_model.py` | [World Model](/engine/world-model.md) | P1 |
| AP-07 | DFS profit-chain finder — TradeHop/ProfitChain, cycle normalize | `chains.py` | [Trade Loops](/strategy/trade-loops.md) | P1 |
| AP-08 | BFS frontier explorer — adjacent-hop fix, ε-greedy pick | `explore.py` | [Frontier Exploration](/strategy/exploration-policy.md) | P1 |
| AP-09 | Priority engine — stay-vs-leave, earn-vs-search, RT-aware upgrade | `priority_engine.py` | [Priority Engine](/engine/priority-engine.md) | P1 |
| AP-10 | WorldSnapshot / Candidate / Decision — ASSESS→SELECT output model | `autopilot.py` | [APP Autopilot Model](/architecture/app-autopilot-model.md) | P1 |
| AP-11 | Cockpit layout — frame_layout tiers, pure-layout split | `spectate_layout.py` | [Trainer Cockpit](/surfaces/trainer-cockpit.md) | P1 |
| AP-12 | Menu crawler — deny-by-default, SAFE_ALLOWLIST, emit_key_if_safe | `menu_crawler.py` | [Menu Map & Introspection](/engine/menu-map-and-introspection.md) | P2 |
| AP-13 | Credits-source discipline — session-atomic read, stale_ms gate | `autopilot.py`, `skills.py` | [APP Autopilot Model](/architecture/app-autopilot-model.md) | P2 |
| AP-14 | Learning dry-run step — menu_signature, propose/compare | `learning/loop.py` | [Candidate Mining](/engine/candidate-mining.md) | P2 |

---

## Pattern Details

### AP-01 — Two-Tier Classify with Stale-Scrollback Discipline

**What it is:** The classification algorithm in `classify.py` splits anchors into two tiers and
evaluates them differently.

- **Gate anchors** (active blocking prompts: `pause_key`, `login_password`, `login_name`,
  `computer`, `warp_confirm`, `main_command`) are matched only against the **current prompt line**
  (the last rendered row). A gate anchor found anywhere deeper in the rendered buffer is stale
  scrollback the server never cleared — not a live prompt.
- **Content anchors** (`sector_display`, `port_trade`, `menu`) describe what _kind_ of screen it
  is and legitimately live a few lines above the prompt — they ARE matched against the full text.

**The `classify_screen(full_text, prompt_line)` signature** reflects this:
gate anchors see only `prompt_line`; content anchors see `full_text`.

**Order matters:** more-specific anchors precede less-specific ones. `computer` (superset pattern
"Computer command [TL=...]") precedes `main_command` ("Command [TL=...]") — order is what lets
the more-specific one win without widening the less-specific pattern. Same for
`cim_report` → `game_select` → gate anchors → content anchors.

**Last-match-wins for multi-signal game_select:** the TWGS game-select screen appears in three
structural variants. Each variant requires multiple signals (header/banner + adjacency check +
qualifying menu body + exclusivity check) all scoped to the range between the anchor and the
current prompt — never to the whole screen. The last (most recent) matching anchor index wins over
a stale earlier one from the same session's scrollback. Key sub-checks:
```
_range_has_no_dash_style_menu(lines, start, end)    # exclusivity: no competing menu shape in range
_range_has_qualifying_game_select_menu(lines, start, end)  # adjacency: distinctive markers present
_range_has_no_menu_after_game_select_markers(lines, start, end)  # exclusivity Round 2: at most 1 trailing option
```

**Feeds:** [Screen Understanding](/engine/screen-understanding.md), login automaton, rule-macro
engine screen-match.

---

### AP-02 — `send_and_confirm` Settle Protocol

**What it is:** `settle.py` provides `send_and_confirm(session, text, confirm_prompt, ...)`, a
disciplined send that refuses to return until the settled screen is _positively confirmed_ — never
a bare idle timeout alone.

**Key invariants:**
1. `rx_at_send` captured **before** `session.send()`. A response arriving before send() returns
   (synchronous fake-session bump) is still treated as "new" since the pre-send baseline.
2. **Stale pre-send match guard:** if `confirm_prompt` already matches what was on screen before
   this send (e.g. a repeating offer-prompt from the prior round), the match is discarded and the
   loop advances one tick. A match is only accepted once `session.rx_count > rx_at_send`.
3. **Stability re-check:** after an initial `confirm_prompt` match, sleep `_CONFIRM_STABILITY_PAUSE_S`
   (0.15 s) and re-verify the pattern is still present. A transitional screen can flash the match
   in one frame and be replaced.
4. **`confirm_prompt=None` path:** when no specific target shape is known (e.g. login automaton
   steps, many macro replay steps), confirm via a stable idle: `wait_for_settle` returns `idle`,
   then re-verify no further bytes arrive during one more stability pause. This is a weaker
   guarantee (can't name the screen arrived) — callers that _can_ name a target shape should
   always supply `confirm_prompt`.
5. **`retry_unstable_idle` flag:** when bytes arrive during the stability pause (a multi-stage
   animation going quiet mid-transition), the default is fail-fast (`False`). Exploration/upgrade
   warps that exhibit this shape pass `retry_unstable_idle=True` to keep re-polling for a stable
   idle within the remaining budget.

**`wait_until_settled(session, ...)` (pre-send freshness gate):** blocks until the session has been
quiet for `debounce_ms` ms. Used at the _read_ side (before acting on what's already on screen) —
distinct from `wait_for_settle`'s post-send "wait for a change then settle" contract.

**Feeds:** [Settle Detection](/architecture/settle-detection.md), login automaton, macro replay,
auto-haggle, App autopilot navigation.

---

### AP-03 — Reactive Login Automaton

**What it is:** `login.py`'s `run_login(session, profile, ...)` drives a session from wherever it
currently is to `target` classification (default `main_command`). It is **reactive and
order-independent**: every iteration re-classifies the current screen and dispatches on that,
so interstitials never desync it.

**Loop structure (pseudocode):**
```python
for step in range(_MAX_STEPS):           # hard step cap
    text = session.render_text()
    prompt = last_row(text)
    cls = classify_screen(text, prompt)
    if cls == target: return cls, step
    action = _decide(cls, text, prompt, profile, state)
    if action is None:                   # unrecognized screen
        stagnant_rounds += 1 if same_signature else 0
        if stagnant_rounds >= _STAGNANT_ROUNDS_LIMIT:
            raise LoginError("automaton_stuck:...")
        session.wait_settle(timeout)
        continue
    send_text, secret, wait_hint = action
    _, _, confirmed = send_and_confirm(session, send_text, ...)
    if not confirmed: fold into stagnant_rounds budget
    else: stagnant_rounds = 0
raise LoginError("automaton_exhausted_steps")
```

**Nuisance table (checked first, before per-classification dispatch):**
Interstitials observed live that can appear at _any_ point and that are safe to dismiss without
understanding where in the flow they appeared:
- `[Pause]` / "press any key" / "-- More --" → blank Enter
- "You have been on today..." → blank Enter
- "Show today's log?" → "N"
- "Do you wish to clear some avoids?" → configurable Y/N (default N)
- "Critical inactivity warning" → blank Enter

**Per-classification dispatch (`_decide`)** covers: `login_name` (outer BBS name vs character name,
disambiguated by prompt wording), `ansi_prompt` → "Y", `game_select` (once per connection — a second
`game_select` on the same connection is always a misfire), `menu` + module-entry wording → "T",
`char_create`, `login_password` (NEW vs RETURNING branch), ship/planet sub-prompts.

**Safety gates:** `game_select_answered` flag prevents answering a second game-select on the same
TCP connection. `allow_register` profile flag gates NEW-character creation. Wrong/stale password
raises `LoginError` (`returning_no_saved_password`) rather than guessing.

**Feeds:** [Login Automaton](/architecture/login-automaton.md).

---

### AP-04 — Skill Record / Replay / Play with Halt-on-Divergence

**What it is:** `skills.py` implements human-demonstrated macro capture and deterministic replay
that halts immediately if reality diverges from what was recorded.

**Record:** `SkillRecorder.record_step(input, wait_prompt, expected_post_class)` accumulates steps.
`stop()` writes `state/skills/<name>.json` with `start_anchor` (the sector the operator was standing
in at capture time) and a `steps` array.

**Skill file schema:**
```json
{
  "name": "...", "source": "recorded", "start_anchor": 1234,
  "steps": [{"input": "...", "wait_prompt": "...", "expected_post_class": "..."}]
}
```

**Replay:** `replay_skill(session, skill, ...)` validates the current sector against `start_anchor`
**before the first send of every cycle** (`_check_start_anchor`). Then for each step:
1. `send_and_confirm(text, confirm_prompt=step["wait_prompt"])` — the step's own recorded `wait_prompt`
2. `classify_screen(text, prompt)` — what screen arrived
3. Compare actual vs `expected_post_class`; if surprised → `raise ReplayDivergence(...)` immediately
4. Check `is_driver_fenced()` (human took the keyboard mid-replay) → `raise ReplayFenced(...)`

**`ReplayDivergence.reason`** distinguishes: `"post_class"` (wrong screen), `"start_anchor_mismatch"`,
`"confirm_failed"` (settle desync). All three are "reality disagreed" — halt, never continue.

**`play_skill(session, skill, cycles, floor=None, ...)` (multi-cycle loop):**
```python
for cycle in range(cycles):
    # Pre-cycle stop-loss: read session.credits_snapshot() (atomic, freshness-gated)
    # Fail-CLOSED: halt with "credits_unknown" if balance never observed or older than stale_ms
    # Halt with "floor_reached" if balance <= floor
    results = replay_skill(...)  # raises on surprise or fence
trace → {"halted": reason, "cycles_completed": N}
```

**Feeds:** [Macros](/engine/macros.md), [APP Autopilot Model](/architecture/app-autopilot-model.md).

---

### AP-05 — Deterministic Haggle — Evidence-Backed Price, Desync Fallback

**What it is:** `haggle.py`'s `run_haggle(session, fair_value, ...)` negotiates the port offer
sub-dialogue only (caller already at a "Your offer [N] ?" prompt).

**Algorithm:**
```
wait_until_settled()           # pre-send freshness gate
haggle = parse_haggle(text)    # extract current_default, direction, baseline
if no current_default: return NO_ACTIVE_HAGGLE

direction = "buy" or "sell"
our_ask = reference ± (open_aggression_pct / 100) * reference   # aggressive open
before_credits = credits_balance(text)                           # baseline for delta check

for round_i in 1..round_cap:
    send_and_confirm(str(our_ask), confirm_prompt=_CONFIRM_RE)
    if not confirmed: accept_default(); return DESYNC_FALLBACK
    haggle = parse_haggle(text)
    if no current_default:                              # dialogue resolved
        price = _evidence_backed_price(...)             # must be positive evidence
        if no evidence: return DESYNC_FALLBACK
        return ACCEPTED at price
    if |current - reference| <= accept_threshold:
        accept_current_default(); price = _evidence_backed_price(...)
        return ACCEPTED
    our_ask = (our_ask + current) / 2.0                # concede toward midpoint

accept_default(); return ROUND_CAP_FALLBACK
```

**`_evidence_backed_price(text, before_credits, direction, candidate_price)` — the trust gate:**
Two independent signals, either suffices:
1. **Credits delta** (`after_credits - before_credits`), signed correctly for direction (buy=negative,
   sell=positive) → report the delta as `final_price` (the honest transacted amount).
2. **Current line is positively a resolution shape** (`_resolution_evidence(text)`) → report
   `candidate_price`. For `Command [TL=` specifically, also requires live-captured acceptance
   phrases or a credits balance line on screen (not merely the Command prompt alone).

Neither passing → `None` → `DESYNC_FALLBACK`. `resolved=True` is never reported without one.

**`_resolution_evidence(text)`:** checks that the _last non-blank line_ matches a recognized
post-haggle shape — not merely somewhere in the full screen. This closes the defect where a stale
`Command [TL=` in scrollback above an unrelated current prompt was accepted as confirmation.

**Live ground truth:** every observed real deal converged within 2 rounds regardless of aggression.
`ROUND_CAP` is generous headroom; the round-cap fallback accepts the current default (never quits
the deal entirely).

**Feeds:** [Auto-Haggle](/engine/auto-haggle.md).

---

### AP-06 — Per-Sector World-Model Store

**What it is:** `world_model.py` stores the warp graph and per-sector knowledge as individual JSON
files, one per sector, under `state/world/<world_id>/sectors/<sector_id>.json`.

**Layout:** `state/world/<world_id>/sectors/<sid>.json` + `<sid>.json.lock` (flock sibling).
One file per sector (not one big `sectors.json` per world) so a single-sector write is O(1)
and per-sector locking lets concurrent writers on _different_ sectors never contend.

**Schema per sector file:**
```json
{
  "sector_id": 1234,
  "warps": [1, 2, 3],
  "port": null,              // or {"class": "1", "commodities": [...], "last_seen_ts": "..."}
  "threats": {"mines": false, "fighters": null},
  "landmarks": ["StarDock"],
  "formation_membership": null,
  "last_seen_ts": "2026-07-25T..."
}
```

**Write discipline:**
```python
with _sector_lock(world_id, sector_id):
    existing = _load_sector_file(...)
    merged = _compute_merged_sector(existing, record, now)
    _save_sector_file(...)  # atomic: write to .tmp, chmod 0600, os.replace()
```

**Field-level upsert semantics (the "additive, last-write-wins" rule):**
- A `record` may be partial — only `sector_id` required.
- Any top-level field _present_ in `record` fully replaces the corresponding stored field.
- Fields _absent_ from `record` are left untouched (a warps-only write must not erase port data).
- **Exception:** `port` dict uses nested merge — sub-fields present in `record["port"]` replace;
  sub-fields absent are preserved. This prevents a plain sector visit (which never observes `class`)
  from clobbering a `class` previously learned from a CIM port report.
- `last_seen_ts` always re-stamps on every write (it is an observation marker, not a change marker).

**`write_from_state(world_id, parsed_state, ...)` write hook:** extracts `warps`/`port`/`threats`
from a `state_parser.parse_state()` dict. Omits `class` from the port sub-dict if unobserved (never
writes `{"class": null}` — a null nested field would silently wipe a previously-learned class via
the nested-merge rule).

**Feeds:** [World Model](/engine/world-model.md).

---

### AP-07 — DFS Profit-Chain Finder

**What it is:** `chains.py` finds profitable closed trade cycles over a set of `TradeHop` edges.
Decoupled from the world-model — callers adapt world-model port data into `TradeHop` objects.

**Data model:**
```python
@dataclass(frozen=True)
class TradeHop:
    frm: int; to: int; commodity: str; margin: float; turns: int = 1

@dataclass(frozen=True)
class ProfitChain:
    sectors: tuple[int, ...]   # closed: first == last
    hops: tuple[TradeHop, ...]
    overall_profit: float; turns: int
    cr_per_turn: float; cr_per_execution: float
```

**Algorithm (pseudocode):**
```python
usable = [h for h in hops if h.margin > 0 and h.turns > 0]
adj = adjacency_dict(usable)          # frm → [hops]

def dfs(start, node, path_nodes, path_hops):
    for hop in adj[node]:
        if hop.to == start and len >= min_hops:
            record(path_nodes, path_hops + [hop])
        elif hop.to not in path_nodes:
            dfs(start, hop.to, ...)

for start in adj.keys():
    dfs(start, start, [start], [])
```

**Cycle normalization:** rotate the closed-cycle tuple so the smallest sector id is first,
enabling deduplication across rotations of the same cycle. When the same cycle is found via
multiple DFS orderings, keep only the highest `cr_per_turn` entry.

**Ranking:** `rank_chains(chains)` sorts by `(len(hops), cr_per_turn)` descending — longer chains
rank above shorter ones at equal cr/turn, ensuring the most strategic route is surfaced first.

**`longest_profit_chain(hops, **kwargs)`:** returns the top-ranked chain or `None`.

**Reborn use:** the chain finder is a read-only planner. The App presents the discovered chain to
the operator; the operator approves; the App replays a taught macro to execute one cycle.

**Feeds:** [Trade Loops](/strategy/trade-loops.md).

---

### AP-08 — BFS Frontier Explorer

**What it is:** `explore.py` plans the next exploration hop over the known warp graph — pure client-side,
no keystrokes emitted.

**Key structures:**
```python
@dataclass(frozen=True)
class FrontierEdge:
    frm: int; to: int; depth: int   # BFS depth from seed sector

@dataclass(frozen=True)
class MapFillPlan:
    next_hop: Optional[FrontierEdge]
    frontier: tuple[FrontierEdge, ...]; known_sectors: int
    unmapped_targets: int; turns_budget_remaining: int
    mode: str   # "explore" | "exploit" | "exhausted"
```

**`frontier_edges(graph, start)`:** BFS from `start` over known warps; collects edges where `to`
is not yet a key in the graph (unmapped sector). Returns edges sorted by `(depth, frm, to)`.

**`pick_frontier_edge(frontier, epsilon, rng, port_seed_frms)` — ε-greedy:**
- With probability `epsilon`: pick a random frontier edge (global map-fill).
- Otherwise (exploit): prefer edges from known-port sectors (`port_seed_frms`) to expand the
  neighborhood of known ports for pair-hunt discovery; fall back to the shallowest overall edge.

**`_adjacent_hop_toward(graph, current, edge)` — the HIGH fix:**
Frontier `edge.frm` may be several known hops away from `current`. The old code returned `edge.to`
directly, firing a warp at an unreachable sector. The fix:
- If `current == edge.frm`: return `edge.to` (genuinely adjacent).
- Otherwise: compute `path_to_sector(graph, current, edge.frm)`, return `path[1]` (first step).
This makes every navigate plan valid in exactly one warp, even when the frontier is distant.

**`path_to_sector(graph, start, goal)`:** BFS shortest-path on the known graph, returns a tuple
of sector ids (`start` inclusive to `goal` inclusive), or `None` if unreachable.

**Recovery when frontier is exhausted:**
1. Hop toward a known StarDock landmark on the graph.
2. Hop toward the highest-out-degree reachable sector (densest — most likely to have unexplored warps).
3. Halt — never a silent empty candidate list.

**Feeds:** [Frontier Exploration](/strategy/exploration-policy.md).

---

### AP-09 — Priority Engine: Stay-vs-Leave, Earn-vs-Search

**What it is:** `priority_engine.py`'s `recommend_actions(...)` ranks `run_chain` / `upgrade` /
`explore` candidates with round-trip-cost-aware upgrade gating.

**`stay_vs_leave_upgrade(chain_cr_per_turn, upgrade_extra_cr_per_turn, travel_cost_rt, payback,
productive_turns)`:**
```
remaining_after = productive_turns - travel_cost_rt - payback
forgone = chain_cr_per_turn * travel_cost_rt
gain = upgrade_extra_cr_per_turn * remaining_after
leave iff gain > forgone
```
Returns `(bool, human_readable_reason)` — never a bare number.

**`prefer_search_over_earn(chain_links, explore_available, min_execute, prefer_search_below)`:**
- `links < min_execute (2)` → must search (execute gated)
- `links >= min_execute` → earn (grind the known chain; a longer chain ranks higher when discovered
  but don't defer earning to hunt one)
Policy: `prefer_search_below` defaults to `min_execute` (no search band unless caller raises it).

**`recommend_actions(...)` scoring:**
- Scores all three kinds, gated or not, with typed `gate_reason` when gated.
- Sorts: ungated by EV descending, gated last; tie-break: `run_chain` > `upgrade` > `explore`.
- Post-sort overrides: if `stay_vs_leave` said "stay", demote `upgrade` below the chain even if
  raw EV is higher. If `earn_vs_search` said "search", promote `explore` above a short chain.
- Returns `PriorityRecommendation(ranked, focus, stay_vs_leave, notes)` — `focus` is the top
  ungated score, or `None` if everything is gated.

**`FighterAffordability.afford_fighters(...)` spending priority:**
1. Reserve `trade_float` (working capital) first.
2. Holds upgrade (weight 75) if known-affordable.
3. Buy fighters (weight 73) with discretionary credits.
4. Ship hull upgrade (weight 60, deferred until ≥4-link chain).

**Feeds:** [Priority Engine](/engine/priority-engine.md).

---

### AP-10 — WorldSnapshot / Candidate / Decision: ASSESS→SELECT Output Model

**What it is:** `autopilot.py` defines the data model for one tick's assessment and selection in a
way that completely decouples the policy from both live I/O and world-model writes.

**`WorldSnapshot` (ASSESS output):** immutable dataclass carrying `sector`, `credits` (from strict
atomic source — never from `parse_state()`), `turns_left`, `current_ship`, `hops`, `ship_catalog`,
`loop`, `stardock_route`, `explore_next_sector`, `hostile_or_pvp`.
SELECT never re-reads live state — it scores only this one snapshot.

**`Candidate` (one SELECT option):**
```python
@dataclass(frozen=True)
class Candidate:
    kind: str              # "run_chain" | "upgrade" | "explore"
    ev_per_turn: float
    rationale: str
    next_sector: Optional[int]   # None if no concrete hop yet
    chain: Optional[ProfitChain]
    upgrade: Optional[UpgradeDecision]
```

**`Decision` (SELECT full output):**
```python
@dataclass(frozen=True)
class Decision:
    ts: float; tick: int; snapshot: WorldSnapshot
    candidates: tuple[Candidate, ...]
    chosen: Optional[Candidate]
    reason: str
    skipped: tuple[str, ...]
    send_outcome: Optional[str]   # None | "held:not_main_command:<cls>" | "sent" | "unconfirmed:..."
```

**`send_outcome` values** expose why a tick may not send: "held:not_main_command" means the live
screen classified to something other than the main command prompt — a sector number send is only
safe when the prompt is confirmed to be that specific shape.

**Credits source discipline (the "strict source" rule):**
`assess()` takes `credits` as a **required keyword argument with no default**. The caller must
supply it from `session.credits_snapshot()` — the atomically-guarded `(last_credits, last_credits_ts)`
pair — not from `parse_state()`. `parse_state()`'s `credits` field matches any "N credits" mention,
including a port's own price quote (same screen, completely wrong value). The strict source
eliminates this pollution. A stale or unobserved balance → `None` → fail-closed skip of
credits-gated candidates. `sector` and `turns_left` remain `parse_state()`-sourced (no documented
lookalike pollution).

**`EconCaps` (tunable safety rails):**
```python
@dataclass(frozen=True)
class EconCaps:
    turn_reserve: int = 50          # gated: do not start a chain that can't complete before this floor
    cash_floor: int = 10_000        # stop-loss: halt if credits fall below
    keep_min_defense_fighters: int = 20
    credits_stale_ms: int = 15_000  # freshness bound for credits_snapshot
    min_margin_per_hop: int = 0     # abort run_chain if per-hop margin falls to this floor
    fighter_reserve: int = ...
```
All values validated in `__post_init__` (negative values raise `ValueError`, preventing silent
bypass of stop-losses via caller-supplied config).

**Reborn framing:** the reborn App uses `WorldSnapshot` / `Candidate` / `Decision` as the **coaching
display** model (what the GOALS and DECISIONS HUD panels show the operator), not as a live
autonomous-execute control path. The App matches on _taught screens_ only; it does not pick a
candidate and fire a keystroke autonomously.

**Feeds:** [APP Autopilot Model](/architecture/app-autopilot-model.md), [Priority Engine](/engine/priority-engine.md).

---

### AP-11 — Cockpit Layout: frame_layout Tiers, Pure-Layout Split

**What it is:** `spectate_layout.py` demonstrates the architectural split between layout computation
and curses rendering — all geometry is computed in pure functions that return named region dicts;
`spectate_app.py` owns the actual window creation.

**`frame_layout(lines, cols, *, needs_attention)` returns named region dicts:**
```python
{
    "mode": "full" | "right_gutter" | "minimal" | "no_border" | "too_small",
    "outer": {y,x,w,h}, "header": ..., "viewport": ...,
    "gutter": ...,    # right HUD panel
    "decisions": ..., "priorities": ..., "menumap": ...,
    "formations": ..., "chain": ..., "ticker": ...,
    "control": ...,   # Trainer Control Panel strip
    "intervention": ...,  # one-row Autopilot-halt strip (when needs_attention)
    "status": ...,
}
```

**Terminal width ladder (cols-driven):**
- `≥ FULL_GUTTER_MIN_COLS (170)`: PRIORITIES left gutter | centered viewport | HUD right gutter
- `≥ RIGHT_GUTTER_MIN_COLS (118)`: viewport + right HUD; left PRIORITIES when `≥ 138`
- `≥ MINIMAL_HEADER_MIN_COLS (82)`: bordered 82×26 viewport, no side gutter
- `≥ 60`: viewport border dropped, game full-bleed/clipped
- `< 60`: "too_small" — refuse to render, show message

**Key constants:**
- `GAME_W, GAME_H = 80, 24` — native TW2002 terminal grid
- `VIEWPORT_W, VIEWPORT_H = 82, 26` — bordered viewport (1-cell border all sides)
- `HUD_GUTTER_W = 44` — right HUD column width (CREDITS + freshness + spark fit on one line)
- `PRIORITIES_W = 44` — left PRIORITIES column
- `CHAIN_VIZ_H = 5` — ASCII chain bubble viz under viewport
- `DECISIONS_MIN_H = 5` — minimum rows before DECISIONS splits from LOG
- `BAND_H_MAX = 10` — max height for the bottom band

**Pure-layout split principle:** every formatting function (`format_sidebar`, `format_ticker_history`,
`compose_dashboard`, `format_status_line`) takes plain data and returns plain strings. No curses
types appear anywhere in `spectate_layout.py`. This makes geometry and formatting unit-testable
without a real terminal.

**Feeds:** [Trainer Cockpit](/surfaces/trainer-cockpit.md), [Spectate & Attach](/surfaces/spectate-and-attach.md).

---

### AP-12 — Menu Crawler: Deny-by-Default, SAFE_ALLOWLIST, emit_key_if_safe

**What it is:** `menu_crawler.py` implements a read-only menu-graph crawler where every
potentially-executable keystroke must pass an affirmative allowlist gate before being sent.

**Architecture (A+C protocol):** The never-commit guarantee lives _outside_ the crawler — in the
human-supervised operator context (disposable zero-asset character, hub-supervised abort). The
crawler's own classification is defense-in-depth, not a completeness guarantee.

**Single chokepoint `emit_key_if_safe(key, label, session)`:**
A key is emittable only if `classify_option_label(label)` affirmatively returns one of the
`SAFE_ALLOWLIST` categories: `view` / `help` / `list` / `display` / `examine` / `back` /
`previous`. Every other classification (state-changing verb, compound label, unrecognized) →
record-the-edge without pressing.

**`classify_option_label(label)`:** matches against:
- `SAFE_ALLOWLIST`: view, help, list, display, examine, back, previous
- `STATE_CHANGING_KEYS`: buy, sell, purchase, attack, deploy, genesis, move, jump, tow, land,
  take, confirm, withdraw, launch, fire, arm, activate, board, quit, exit, leave, ...

**Accepted residuals (by design):** prefix-affixed verb forms ("Repurchase"), agent-nouns
("Buyer"), homographs ("Board" as noun vs verb) are accepted as safe rather than adding an ever-
expanding denylist. The A+C protocol bounds the worst case.

**BFS traversal via recorded replay:** never navigates forward from the current screen; instead,
replays the path from the session start each time to reach a new unexplored node. This means
"quit" / "back" options are recorded-not-pressed — the traversal always replays from start.

**Bare Enter is never emitted.** Even a synthetic `("", "Enter")` option discovered on a menu is
always record-without-pressing.

**Feeds:** [Menu Map & Introspection](/engine/menu-map-and-introspection.md).

---

### AP-13 — Credits-Source Discipline

**What it is:** A recurring cross-cutting discipline in `autopilot.py`, `skills.py`, and
`loop_player.py` — everywhere a credits balance is used to gate a decision.

**The source:** `session.credits_snapshot()` → `(last_credits, last_credits_ts)` — an atomic read
of the last-observed balance and its timestamp. This balance is set by `session.observe_credits(text)`
called on every settled render (including mid-replay and post-move steps).

**Stale check:**
```python
bal, ts = session.credits_snapshot()
age_ms = (time.monotonic() - ts) * 1000 if ts is not None else None
fresh = bal is not None and age_ms is not None and age_ms <= credits_stale_ms
if not fresh: halt("credits_unknown")
```

**Why not `parse_state().get("credits")`?** `parse_state()` matches any "N credits" mention,
including a port's price quote on the same screen ("We'll buy 100 units for 4,187 credits"). Using
`parse_state()` for a cash-floor stop-loss means the stop-loss can be defeated by a price quote on
the wrong screen — exactly what happened live before this was fixed.

**One macro-cycle exposure:** `credits_snapshot()` may predate the current cycle's last buy by up
to `credits_stale_ms` (default 15s). A per-spend "confirmed since last buy" gate is the buy-flow's
own responsibility; `credits_snapshot()` is the per-cycle floor gate.

**Feeds:** [APP Autopilot Model](/architecture/app-autopilot-model.md), [Macros](/engine/macros.md).

---

### AP-14 — Learning Dry-Run Step

**What it is:** `learning/loop.py`'s `dry_run_step(...)` implements the observe→propose→verify
cycle for the candidate-mining layer — structurally incapable of executing.

**`menu_signature(screen_text)` → 16-char hex:** a short hash of the rendered screen used as a
state key. The signature is the state identity in the rule/transition store — not the full text.
Two screens with the same layout but different dynamic values produce the same signature only if
the layout itself is identical (no normalization of variable values).

**`dry_run_step(before_screen, after_screen, known_actions, prior_rules, ...)` trace:**
```python
blocked = blocked_actions_for_context(authority, human_combat_confirmed)
candidates = propose_candidates(before_sig, known_actions, prior_rules, blocked_actions)
if after_screen and tried_action:
    verify = compare_transition(before_sig, after_sig, expected_transition, prior_confidence)
    proposed_rule_update = {"state_signature": before_sig, "tried_action": selected,
                            "observed_transition": verify["observed_transition"],
                            "confidence": verify["new_confidence"]}
return trace   # never sends, never writes store
```

The trace object (`mode: "dry_run"`, `executed: False`) is the AI Teacher's proposed rule update.
The human reviews, approves, and the approved rule enters the library — the loop itself never writes.

**Feeds:** [Candidate Mining](/engine/candidate-mining.md), [AI Teacher](/engine/ai-teacher.md).

---

## Negative Patterns — Do Not Port

The following exist in the archive but are incompatible with the reborn vision and must **not** be
revived in product code or canon:

| Item | Archive Location | Why Not |
|------|-----------------|---------|
| `ai_pilot` mode / `profile.autonomous` flag / `AutopilotGateError` | `autopilot.py`, `credentials.py` | AI-first framing; reborn App drives only taught screens, no `autonomous` opt-in flag needed |
| EV-every-tick live run-loop (`AutopilotLoop.start()`) | `autopilot.py` | No autonomous loop in reborn; App fires macros on known+taught screens only |
| `actor="trainer"` ledger enum | `skills.py`, `ledger.py` | Reborn actor set is `{app, human}` only; AI is a rule author, never a live sender |
| `loop_player.LoopPlayer` autonomous background loop | `loop_player.py` | Same; reborn: App plays macros per cycle, always on a known screen, with stop-on-unknown |
| TWGS multi-server registration / name bank (`register_with_name_bank`) | `login.py`, `name_bank.py` | Autonomous character creation; reborn login drives only to an existing character |
| `_execute()` / `live_tick()` run_chain/upgrade send path | `autopilot.py` | Navigation by sector number is safe, but running a full trade chain autonomously is not yet a taught behavior |
| `learning/loop.py` `authority: "ai"` execute path | `learning/loop.py` | Learning proposes only; never executes |
| `tw record`/`tw replay` exact verb names | `cli.py` | UX changes to Teach (A), Record (R), Replay/Teach (T) hotkeys in cockpit; patterns stay, verb surface changes |
| `spectate_layout.py` `format_ticker_entry` `answered_*` pairing as-is | `spectate_layout.py` | Shape is right; field names may differ in reborn event schema |

---

## Citations

- `archive/pre-rebirth-2026-07-23/code/twclient/classify.py` — AP-01
- `archive/pre-rebirth-2026-07-23/code/twclient/settle.py` — AP-02
- `archive/pre-rebirth-2026-07-23/code/twclient/login.py` — AP-03
- `archive/pre-rebirth-2026-07-23/code/twclient/skills.py` — AP-04
- `archive/pre-rebirth-2026-07-23/code/twclient/haggle.py` — AP-05
- `archive/pre-rebirth-2026-07-23/code/twclient/world_model.py` — AP-06
- `archive/pre-rebirth-2026-07-23/code/twclient/chains.py` — AP-07
- `archive/pre-rebirth-2026-07-23/code/twclient/explore.py` — AP-08
- `archive/pre-rebirth-2026-07-23/code/twclient/priority_engine.py` — AP-09
- `archive/pre-rebirth-2026-07-23/code/twclient/autopilot.py` — AP-10, AP-13
- `archive/pre-rebirth-2026-07-23/code/twclient/spectate_layout.py` — AP-11
- `archive/pre-rebirth-2026-07-23/code/twclient/menu_crawler.py` — AP-12
- `archive/pre-rebirth-2026-07-23/code/twclient/skills.py` — AP-13
- `archive/pre-rebirth-2026-07-23/code/twclient/learning/loop.py` — AP-14
