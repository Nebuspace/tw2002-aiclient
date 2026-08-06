---
type: Reference
title: Toll & Defense Math (NPC-only)
description: Fight/pay/reroute decision math feeding the fighter-toll guarded rule — NPC targets only, where combat is a prime escalation moment.
tags: [strategy, combat, defense, toll, npc-only, hypothesis]
timestamp: 2026-08-06T02:02:00Z
---

# Scope

This is the decision math for **NPC-controlled** hazards — deployed corp fighters
guarding a sector ("toll" sectors) and mines encountered en route — and **nothing
else**. Player-vs-player combat is out of scope by construction: the ethos treats a
combat screen involving a real player as a hard STOP-and-escalate that only the human
resolves in the moment (single source: `/doctrine/alignment-and-conduct.md`). The
formulas here never justify, trigger, or soften any move against another player.

Within the reborn vision this concept is **spec, not a driver**. It feeds three
consumers:

1. **Rule-guards** — the deterministic fighter-toll guarded rule (a built-in archetype
   of `/architecture/rule-macro-engine.md`) resolves safe exits of a live toll dialogue
   and STOPS on anything it cannot prove safe. **Exception (Max GO 2026-07-28):** under
   the `force_share` gate below, the guard may autonomously Attack on **NPC** tolls.
2. **Priority scoring** — reroute-vs-fight EV is a *ranking/ordering* input to
   `/engine/priority-engine.md`; it orders which taught behaviors or human suggestions
   surface. It is **never** a live per-cycle action-picker that lets a computed EV win
   over an unrecognized or combat screen **below** the auto-Attack gate.
3. **Human coaching** — the on-demand AI teacher and the cockpit FOCUS panel use this
   math to explain a situation retrospectively. Coaching never sends a keystroke; the
   guarded rule may, under the gate above.

**Every number below is a HYPOTHESIS** unless Max has ratified it as an operational
default. Encode each as a configurable parameter, never a hardcoded constant. See
**Verification status**. `force_share_auto_attack = 0.90` is Max-ratified (2026-07-28)
as the operational auto-Attack threshold; still configurable.

# Schema — the decision parameters

Toll/defense math is a small set of portable *semantics*. Author the semantics; leave
the per-server values to configuration and to live observation folded into the world
model.

| Parameter | Value / status | Meaning / role |
|---|---|---|
| `reserve_floor` (deploy/sell clamp) | 5 aboard — **LIVE** tip `DEFAULT_FIGHTER_RESERVE` in `session/fighter_toll_policy.py` | Small early-game floor: never sell/deploy a ship below this, so a lone toll can still be answered after routine trade. |
| `winnable_enemy_band` | ≤ 3 enemies — tip default `DEFAULT_AUTO_ATTACK_MAX_ENEMY` (config) | "Single or few." Above this, auto-Attack is forbidden even if force_share is high. |
| `force_share_auto_attack` | ≥ 0.90 [Max GO 2026-07-28] | Autonomous NPC Attack allowed when `force_share = own / (own + enemy) ≥` this value **and** `enemy ≤ winnable_enemy_band` **and** both counts are present. Name the ratio **force_share** (not `win_est`). |

**Stripped (WO-ESCALATE-TOLL-DEFENSE-UNBUILT-CONSTANTS · Max Option B 2026-08-05).** The following
third-party / design-history numbers are **not** canon constants and must not be treated as
computable today: `shield_reserve_multiplier` (was 2:1), `missile_bypass_fraction` (was ~7%),
`keep_min_defense_fighters` / `defense_fighter_floor` (was 20), plus the
`min_fighters_to_win` formula, surrender-ratio bands, and `min_shield_reserve` % floor that
depended on them. They remain research notes only until a real design pass measures live combat.
Do not encode them into tip code or coach them as operational math. Only the LIVE / Max-ratified
rows above drive the auto-Attack gate and quantity clamps.

# Toll-dialogue guard behavior (I5)

The live corp-fighter toll surfaces as an `Option? (A,D,I,R[,P],S,?):?` prompt (Pay is
absent on some live tolls — the detector treats `P` as optional). The deterministic
guard's contract, honoring the reborn stop-on-unknown invariant re-validated **every
cycle**:

- **0 fighters aboard ⇒ Retreat (`R`).** A hopeless toll has one safe non-engaging exit.
- **Never Pay (`P`).** Paying a toll spends money on a live game path; it requires an
  explicit human GO and is never auto-selected. The parameter that would allow it exists
  only so tests can prove Pay is never chosen by default.
- **Counts unreadable (vs-line scrolled off, unparsed) ⇒ Retreat**, the safe exit —
  never a blind engage, never Pay. Holding forever would wedge the session; Retreat both
  clears the wedge and stays non-engaging. Parsed zero is a present count; missing is not.
- **Autonomous NPC Attack (`A`) when all of:** both fighter counts are present;
  `enemy ≤ winnable_enemy_band`; `force_share = own/(own+enemy) ≥ force_share_auto_attack`
  (default 0.90); target is NPC/environmental (not PvP). The follow-up
  `How many fighters…` prompt may auto-commit a clamped quantity under the same
  reserve floors **only when counts remain present on that screen**. If counts are
  unreadable at the quantity prompt (a distinct frame — qty screens often omit
  `Option?`): **never** commit `max_avail` / the full complement; **fail closed** —
  typed STOP that **owns the prompt** so idle/`[0]` cannot re-fire Attack forever
  (bare unanswered STOP is unsafe; Retreat is unavailable after `A`). **Otherwise
  Retreat (`R`)** at `Option?` (or STOP if the frame is unrecognized /
  mid-fight mismatch). **PvP ⇒ hard STOP.** Weaker force_share remains a STOP-and-escalate
  or Retreat — never an EV-picked Attack below the gate. (Max GO 2026-07-28 supersedes
  earlier reborn prose that framed *all* engaging combat as human-only.)
- **Mines** threaten cargo/ship loss on entry rather than presenting a dialogue. A
  known/suspected mined sector on a route is a route-hazard guard input that STOPS the
  planned crossing and escalates — it is not silently driven through.

The live reserve floor today is **`DEFAULT_FIGHTER_RESERVE` (5)** — a quantity
**clamp** on deploy/sell / auto-Attack commits so the ship is never left
defenceless below that floor. It is not itself a combat trigger. A larger
upgrade-path defense floor is **not canonized** (stripped Option B) — do not invent
`defense_fighter_floor` / `keep_min_defense_fighters` on tip.

# Reroute-vs-fight EV — a coaching / priority input

"We can win" does **not** imply "we should fight" when below the auto-Attack gate. The
cheaper move is frequently to reroute one or two hops around the hazard, especially when
a fight would burn fighters/shields that then cost turns and credits to replace.

- Compute the reroute turn-cost (extra hops) against the *expected* cost of fighting
  (fighters/shields likely lost + their replacement turns/credits).
- Surface the comparison as: a **priority ranking** of taught behaviors (a reroute macro
  vs. escalate-to-fight) in `/engine/priority-engine.md`, and as **coaching** in the
  cockpit / on-demand teacher.
- This EV **ranks and orders**; it never executes a fight below `force_share_auto_attack`.
  It cannot promote a fight over a STOP, and it never runs a live cycle as an action-picker.
  Depletion or a hazard on the route is a STOP-guard that escalates — never an autonomous
  reroute-and-keep-driving.

# NPC / PvP boundary (hard)

All math on this page is scoped to NPC/environmental hazards. The moment a real player is
involved — attacker or victim — this page does not apply and the client STOPS for the
human. Reliable attacker/victim identification is itself a first-class hazard: unreliable
ID ⇒ recommend nothing, escalate. The conduct rule that governs this boundary lives in
`/doctrine/alignment-and-conduct.md` (the single canonical source); this page is math
only.

# Steps (how a toll/hazard is worked)

1. Before entering a known-hazardous sector, read its last-known defender count from the
   world model's `threats.fighters` / `threats.mines` (`/engine/world-model.md`), or take
   a fresh density-scan reading (`/strategy/exploration-policy.md`) if the record is
   stale.
2. Compare observed own vs enemy fighter counts (and any shields the screen shows) against the
   LIVE `force_share` / band gate — as *information* for coaching and priority ranking, not as a
   trigger to invent fight math from stripped hypotheses.
3. If a taught reroute looks cheaper than engaging **and** force_share is below the auto-Attack
   gate, the priority layer ranks the reroute macro above escalation and the human is
   coached toward it. Do not compute expected fight-cost from unconfirmed bypass/shield multipliers.
4. On the live toll dialogue: Never Pay; 0 own fighters ⇒ Retreat; unparseable ⇒ Retreat;
   if `force_share` gate + band + NPC hold ⇒ Attack + quantity clamp (`DEFAULT_FIGHTER_RESERVE`);
   else Retreat or STOP-and-escalate.
5. Record the outcome (fighters/shields spent, sector, result) so the world model's threat
   entry stays current for the next pass.

# Code grounding

Grounded against `fighter_toll_policy.py` and `world_model.py` (DOCS WIN — divergences
recorded, not silently conformed to).

- **World-model threat state.** `world_model.py` persists `threats: {"mines": bool,
  "fighters": int | None}` per sector (`_default_sector`), last-write-wins per field with
  `last_seen_ts` always advancing on a genuine observation. This is the store the toll
  math reads for a last-known defender count; a `None` fighters field means "never
  observed here" and should drive a fresh scan or a conservative STOP, not an assumption
  of "safe."
- **Toll dialogue detection & resolution.** `fighter_toll_policy.py` parses the
  `Option?` prompt and the `Your fighters: N vs. theirs: M` line (falling back to the
  `Fighters: N (…)[Toll]` banner when the vs-line has scrolled off pyte's viewport). Its
  guard correctly refuses Pay unconditionally, Retreats on 0 fighters, and Retreats when
  counts are unparseable — all reborn-aligned safe exits. `max_deployable` /
  `clamp_deploy_or_sell_qty` implement the reserve-floor clamps.

## Code divergence

- **`force_share` auto-Attack gate — RESOLVED on tip (WO-CANON-DRAFT-TOLL-DEFENSE-STALE-DIVERGENCE-NOTE).**
  Tip `session/fighter_toll_policy.py` (`decide_encounter` / `decide_quantity` /
  `next_encounter_input`; Max GO 2026-07-28) Attack-selects `"A"` only when
  `force_share ≥ force_share_auto_attack` (default 0.90) ∧ `enemy ≤ winnable_enemy_band`
  ∧ both counts present ∧ NPC-only; quantity commit is clamped and **never**
  `max_avail` when counts are unreadable (STOP owns the prompt — no `A` re-fire loop).
  Retreat / never-Pay / unparseable-at-Option remain. The old
  `decide_fighter_option` / `next_fighter_option_input` names are gone; do not cite them
  as missing rails. Separate design question (human-approval before any auto-Attack)
  stays outside this tip-catchup — see gated escalate rows if present.
- **Autopilot per-cycle EV selection + "never idle" appetite.** The legacy autopilot
  picks an action each cycle by expected value, backed by an `EXPLORE_BASELINE_EV`
  floor that keeps it moving rather than ever idling. Under the reborn vision the
  reroute-vs-fight EV is a *ranking/coaching* input only; it must not act as a live
  per-cycle action-picker, and the "never idle / keep-driving" appetite is retired in
  favor of depletion/hazard STOP-guards. Tip has no `autopilot.py`; `EXPLORE_BASELINE_EV`
  is suggestion-only in `focus_status.py` (display subdivergence closed elsewhere).
- **`trade_driver`'s autonomous chain runner** executes a taught chain end-to-end under
  fail-closed arm predicates (`is_armed` / `should_abort` via `TradeChainRunner` / ADR-003).
  **Option C fact-find (2026-08-06):** there is **no** kernel `screen_match` field check inside
  `run_chain()`, but tip **does** re-validate the live screen every navigation step and at port
  cascade prompts via `classify_screen` + `ChainHold` on unexpected classes
  (`_navigate` requires `main_command` before each warp send; warp_confirm / avoid-DANGER handled;
  `_visit_port` HOLDs on unexpected cascade screens). Mid-chain toll/mine still STOP unless the
  fighter-toll guard's force_share gate applies — the runner does not invent via EV. See
  `WO-ESCALATE-TRADE-DRIVER-CHAIN-RUNNER-SCREEN-MATCH-NO-CANON`.
- **§22 / TW-23 capstone re-scope.** The original autonomous-trainer capstone framed the
  toll/defense math as an input to an EV-maximizing pilot. It is re-scoped here to a
  guard + priority-scoring + coaching spec, with the narrow Max-ratified auto-Attack gate
  above.

# Verification status

**Operational (LIVE / Max-ratified):** `force_share_auto_attack = 0.90`,
`DEFAULT_FIGHTER_RESERVE = 5`, and the tip `winnable_enemy_band` default. These are the only
numbers this concept treats as computable for auto-Attack / clamps today.

**Stripped / UNVERIFIED (Option B):** minimum-fighters formula, 2:1 shield reserve,
surrender-ratio bands, ~7% missile-bypass, ~10% shield-reserve floor, and
`keep_min_defense_fighters=20` are **not** canon — third-party research notes only until a
measured design pass. Do not hardcode them; do not coach them as if tip implements them.

# Citations

- Design history §16.2 — toll decision rule: minimum-fighters formula, surrender-ratio
  bands, missile-bypass rate, shield reserve.
- Design history §18 — alignment ethos: player-combat is human-directed/coached, never an
  autonomous trigger.
- Max GO 2026-07-28 — NPC auto-Attack at force_share ≥ 0.90 with winnable_enemy_band;
  DECISION RESOLVED-COMBAT-AUTOFIGHT-90.
- Reimagined from the raw material at `knowledge/strategies/toll-and-defense-math.md`
  (CARRY-WITH-CHANGES; re-rooted in the reborn vision — priority ranks/orders, guards +
  scoring + coaching, gated auto-Attack).
- Code modules (plain-text references): `fighter_toll_policy.py` (toll-dialogue guard),
  `world_model.py` (per-sector `threats` state).

# Cross-links

- `/architecture/rule-macro-engine.md` — fighter-toll = a built-in guarded-rule archetype.
- `/architecture/control-and-escalation.md` — the STOP-and-escalate mechanic and the
  reason-code catalog a combat halt renders.
- `/engine/world-model.md` — the `threats` state this math reads.
- `/engine/priority-engine.md` — where reroute-vs-fight EV ranks/orders (never picks).
- `/strategy/exploration-policy.md` — fresh density-scan when a threat record is stale.
- `/doctrine/alignment-and-conduct.md` — the conduct rule; NPC/PvP boundary; single source.
- `/doctrine/action-safety-guards.md` — the byte-level guards (never-Pay, reserve clamps,
  novelty-halt) this math attaches to.
