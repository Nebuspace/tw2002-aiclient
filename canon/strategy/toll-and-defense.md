---
type: Reference
title: Toll & Defense Math (NPC-only)
description: Fight/pay/reroute decision math feeding the fighter-toll guarded rule — NPC targets only, where combat is a prime escalation moment.
tags: [strategy, combat, defense, toll, npc-only, hypothesis]
timestamp: 2026-07-28T22:36:00Z
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

| Parameter | Hypothesized value | Meaning / role |
|---|---|---|
| `min_fighters_to_win` | `(defender_fighters × defender_odds) ÷ your_odds` [hypothesis] | Threshold that a fight is *survivable in principle*. Coaching / ranking input — not a substitute for the auto-Attack gate. |
| `shield_reserve_multiplier` | 2:1 [hypothesis] | Shields count double their nominal value toward effective defense in the min-fighters comparison. |
| `surrender_upside` | ~10× ⇒ tends free/full surrender; ~5× ⇒ ~even odds of partial; ~2× ⇒ smaller chance [hypothesis] | Approximate bands by attack-strength ratio. Bands, not guarantees; coaching input only. |
| `missile_bypass_fraction` | ~7% [hypothesis] | Fraction of missile damage that bypasses fighter defense directly — the argument for a standing shield reserve even when fighters alone look sufficient. |
| `min_shield_reserve` | ~10% of fighter count [hypothesis] | Standing shield floor to blunt the bypass-damage risk. |
| `reserve_floor` (deploy/sell clamp) | 5 aboard [hypothesis: `DEFAULT_FIGHTER_RESERVE`] | Small early-game floor: never sell/deploy a ship below this, so a lone toll can still be answered after routine trade. |
| `defense_fighter_floor` (upgrade) | 20 aboard [hypothesis: `keep_min_defense_fighters`] | Larger standing defense floor on the upgrade path; distinct from the small reserve above. |
| `winnable_enemy_band` | ≤ 3 enemies [hypothesis: `DEFAULT_AUTO_ATTACK_MAX_ENEMY`] | "Single or few." Above this, auto-Attack is forbidden even if force_share is high. |
| `force_share_auto_attack` | ≥ 0.90 [Max GO 2026-07-28] | Autonomous NPC Attack allowed when `force_share = own / (own + enemy) ≥` this value **and** `enemy ≤ winnable_enemy_band` **and** both counts are present. Name the ratio **force_share** (not `win_est`). |

`your_odds` / `defender_odds` are the combat-odds terms of the server's fight
resolution; they are server semantics, not fixed numbers, and belong in configuration.
They inform coaching/`min_fighters_to_win`; they do **not** replace the `force_share` gate.

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

The reserve floors (`reserve_floor`, `defense_fighter_floor`) are quantity **clamps**:
they bound how many fighters a deploy/sell **or** an auto-Attack quantity commit may
shed/spend so the ship is never left defenceless below the configured floor. They are
not themselves a combat trigger.

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
2. Compute `min_fighters_to_win` (with the 2:1 shield reserve) and compare against the
   current fighter/shield loadout — as *information*, not as a trigger below the gate.
3. If reroute turn-cost < expected fight-cost **and** force_share is below the auto-Attack
   gate, the priority layer ranks the reroute macro above escalation and the human is
   coached toward it.
4. On the live toll dialogue: Never Pay; 0 own fighters ⇒ Retreat; unparseable ⇒ Retreat;
   if `force_share` gate + band + NPC hold ⇒ Attack + quantity clamp; else Retreat or
   STOP-and-escalate. Keep `min_shield_reserve` coaching visible.
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

- **`fighter_toll_policy.decide_fighter_option` auto-selects Attack (`"A"`).** Target
  (Max GO 2026-07-28): Attack only when `force_share ≥ force_share_auto_attack` (default
  0.90) ∧ `enemy ≤ winnable_enemy_band` ∧ both counts present ∧ NPC-only; then
  `next_fighter_option_input` may auto-commit a clamped quantity on `How many fighters…`
  only when counts are still present; unreadable at qty ⇒ never `max_avail`, STOP that
  owns the prompt (no `A` re-fire loop). Keep Retreat / never-Pay / unparseable-at-Option.
  Re-validate screen-match every tick so a mid-fight unrecognized frame halts.
- **Autopilot per-cycle EV selection + "never idle" appetite.** The legacy autopilot
  picks an action each cycle by expected value, backed by an `EXPLORE_BASELINE_EV`
  floor that keeps it moving rather than ever idling. Under the reborn vision the
  reroute-vs-fight EV is a *ranking/coaching* input only; it must not act as a live
  per-cycle action-picker, and the "never idle / keep-driving" appetite is retired in
  favor of depletion/hazard STOP-guards.
- **`trade_driver`'s autonomous chain runner** executes a taught chain end-to-end on its
  own. The reborn target is a HUMAN-ARMED taught behavior that re-validates screen_match
  every tick and halts on the first unrecognized frame — a toll/mine encountered mid-chain
  is a STOP unless the fighter-toll guard's force_share gate applies, not something the
  runner invents via EV.
- **§22 / TW-23 capstone re-scope.** The original autonomous-trainer capstone framed the
  toll/defense math as an input to an EV-maximizing pilot. It is re-scoped here to a
  guard + priority-scoring + coaching spec, with the narrow Max-ratified auto-Attack gate
  above.

# Verification status

UNVERIFIED against the live game for most numeric hypotheses. The minimum-fighters
formula, the 2:1 shield reserve, the surrender-ratio bands (~10× / ~5× / ~2×), the ~7%
missile-bypass fraction, the ~10% shield-reserve floor, and the reserve defaults (5 / 20 /
≤3) are carried from third-party TW2002-variant strategy-guide research and from the
current client defaults, and must be confirmed against direct in-game combat observation
before being relied on operationally. Encode every one as a configurable parameter, never
a hardcoded constant. **`force_share_auto_attack = 0.90` is Max-ratified as the
operational default** (still overridable in config).

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
