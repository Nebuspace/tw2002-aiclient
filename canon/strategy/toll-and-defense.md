---
type: Reference
title: Toll & Defense Math (NPC-only)
description: Fight/pay/reroute decision math feeding the fighter-toll guarded rule — NPC targets only, where combat is a prime escalation moment.
tags: [strategy, combat, defense, toll, npc-only, hypothesis]
timestamp: 2026-07-23T20:20:03Z
---

# Scope

This is the decision math for **NPC-controlled** hazards — deployed corp fighters
guarding a sector ("toll" sectors) and mines encountered en route — and **nothing
else**. Player-vs-player combat is out of scope by construction: the ethos treats a
combat screen involving a real player as a hard STOP-and-escalate that only the human
resolves in the moment (single source: `/doctrine/alignment-and-conduct.md`). The
formulas here never justify, trigger, or soften any move against another player.

Within the reborn vision this concept is **spec, not a driver**. It feeds three
consumers, none of which is an autonomous pilot:

1. **Rule-guards** — the deterministic fighter-toll guarded rule (a built-in archetype
   of `/architecture/rule-macro-engine.md`) resolves the safe, non-engaging exits of a
   live toll dialogue and STOPS on anything it cannot prove safe.
2. **Priority scoring** — reroute-vs-fight EV is a *ranking/ordering* input to
   `/engine/priority-engine.md`; it orders which taught behaviors or human suggestions
   surface. It is **never** a live per-cycle action-picker that lets a computed EV win
   over an unrecognized or combat screen.
3. **Human coaching** — the on-demand AI teacher and the cockpit FOCUS panel use this
   math to explain a situation retrospectively. The AI never sends a keystroke.

**Every number below is a HYPOTHESIS.** Encode each as a configurable coaching /
scoring parameter, never a hardcoded constant. See **Verification status**.

# Schema — the decision parameters

Toll/defense math is a small set of portable *semantics*. Author the semantics; leave
the per-server values to configuration and to live observation folded into the world
model.

| Parameter | Hypothesized value | Meaning / role |
|---|---|---|
| `min_fighters_to_win` | `(defender_fighters × defender_odds) ÷ your_odds` [hypothesis] | Threshold that a fight is *survivable in principle*. Not a green light to fight — see the guard boundary below. |
| `shield_reserve_multiplier` | 2:1 [hypothesis] | Shields count double their nominal value toward effective defense in the min-fighters comparison. |
| `surrender_upside` | ~10× ⇒ tends free/full surrender; ~5× ⇒ ~even odds of partial; ~2× ⇒ smaller chance [hypothesis] | Approximate bands by attack-strength ratio. Bands, not guarantees; coaching input only. |
| `missile_bypass_fraction` | ~7% [hypothesis] | Fraction of missile damage that bypasses fighter defense directly — the argument for a standing shield reserve even when fighters alone look sufficient. |
| `min_shield_reserve` | ~10% of fighter count [hypothesis] | Standing shield floor to blunt the bypass-damage risk. |
| `reserve_floor` (deploy/sell clamp) | 5 aboard [hypothesis: `DEFAULT_FIGHTER_RESERVE`] | Small early-game floor: never sell/deploy a ship below this, so a lone toll can still be answered after routine trade. |
| `defense_fighter_floor` (upgrade) | 20 aboard [hypothesis: `keep_min_defense_fighters`] | Larger standing defense floor on the upgrade path; distinct from the small reserve above. |
| `winnable_enemy_band` | ≤ 3 enemies [hypothesis: `DEFAULT_AUTO_ATTACK_MAX_ENEMY`] | "Single or few." Above this, a fight is not *clearly* winnable — the guard must not treat it as safe. |

`your_odds` / `defender_odds` are the combat-odds terms of the server's fight
resolution; they are server semantics, not fixed numbers, and belong in configuration.

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
  clears the wedge and stays non-engaging.
- **Actually engaging combat is a STOP-and-escalate, not an autonomous move.** Under the
  reborn vision a hazard-crossing that requires *fighting* is a prime escalation moment:
  the app hands the human the keyboard with a typed reason code (catalog owned by
  `/architecture/control-and-escalation.md`), rather than committing fighters on its own.
  The math here tells the human (and the priority layer) whether the fight is winnable
  and at what reserve; the *decision to fight* is the human's. See **Code divergence**.
- **Mines** threaten cargo/ship loss on entry rather than presenting a dialogue. A
  known/suspected mined sector on a route is a route-hazard guard input that STOPS the
  planned crossing and escalates — it is not silently driven through.

The reserve floors (`reserve_floor`, `defense_fighter_floor`) are deploy/sell **clamps**:
they bound how many fighters a routine deploy-or-sell may shed so the ship is never left
defenceless below the configured floor. They constrain non-combat quantity prompts; they
are not a combat trigger.

# Reroute-vs-fight EV — a coaching / priority input

"We can win" does **not** imply "we should fight." The cheaper move is frequently to
reroute one or two hops around the hazard, especially when a fight would burn
fighters/shields that then cost turns and credits to replace.

- Compute the reroute turn-cost (extra hops) against the *expected* cost of fighting
  (fighters/shields likely lost + their replacement turns/credits).
- Surface the comparison as: a **priority ranking** of taught behaviors (a reroute macro
  vs. escalate-to-fight) in `/engine/priority-engine.md`, and as **coaching** in the
  cockpit / on-demand teacher.
- This EV **ranks and orders**; it never executes. It cannot promote a fight over a
  STOP, and it never runs a live cycle. Depletion or a hazard on the route is a
  STOP-guard that escalates — never an autonomous reroute-and-keep-driving.

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
   current fighter/shield loadout — as *information*, not as a trigger.
3. If reroute turn-cost < expected fight-cost, the priority layer ranks the reroute macro
   above escalation and the human is coached toward it.
4. On the live toll dialogue, the guard resolves only the safe non-engaging exits
   (Retreat; never Pay); any fight is a STOP-and-escalate the human confirms, ensuring the
   `min_shield_reserve` is met first.
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

- **`fighter_toll_policy.decide_fighter_option` auto-selects Attack (`"A"`) on a
  "clearly winnable" band** (`theirs <= max_enemy and yours >= max(theirs, 1)`, i.e.
  ≤ 3 enemies with at least parity), and `next_fighter_option_input` then auto-commits a
  fighter quantity on the follow-up `How many fighters…` prompt. This is **autonomous
  NPC combat**. The reborn vision reframes a hazard-crossing that requires *fighting* as a
  prime escalation moment: the guard should resolve only the non-engaging exits
  (Retreat / never Pay) deterministically and STOP-and-escalate to the human for the
  actual decision to attack, rather than committing fighters on its own. Target: keep the
  Retreat/never-Pay guard, demote auto-Attack to a STOP+escalate (with this math shown to
  the human), and re-validate screen-match every tick so a mid-fight unrecognized frame
  halts.
- **Autopilot per-cycle EV selection + "never idle" appetite.** The legacy autopilot
  picks an action each cycle by expected value, backed by an `EXPLORE_BASELINE_EV`
  floor that keeps it moving rather than ever idling. Under the reborn vision the
  reroute-vs-fight EV is a *ranking/coaching* input only; it must not act as a live
  per-cycle action-picker, and the "never idle / keep-driving" appetite is retired in
  favor of depletion/hazard STOP-guards.
- **`trade_driver`'s autonomous chain runner** executes a taught chain end-to-end on its
  own. The reborn target is a HUMAN-ARMED taught behavior that re-validates screen_match
  every tick and halts on the first unrecognized frame — a toll/mine encountered mid-chain
  is a STOP, not something the runner fights or reroutes through autonomously.
- **§22 / TW-23 capstone re-scope.** The original autonomous-trainer capstone framed the
  toll/defense math as an input to an EV-maximizing pilot. It is re-scoped here to a
  guard + priority-scoring + coaching spec with no autonomous-driving surface.

# Verification status

UNVERIFIED against the live game. The minimum-fighters formula, the 2:1 shield reserve,
the surrender-ratio bands (~10× / ~5× / ~2×), the ~7% missile-bypass fraction, the ~10%
shield-reserve floor, and the reserve defaults (5 / 20 / ≤3) are carried from third-party
TW2002-variant strategy-guide research and from the current client defaults, and must be
confirmed against direct in-game combat observation before being relied on operationally.
Encode every one as a configurable coaching/scoring parameter, never a hardcoded constant.

# Citations

- Design history §16.2 — toll decision rule: minimum-fighters formula, surrender-ratio
  bands, missile-bypass rate, shield reserve.
- Design history §18 — alignment ethos: player-combat is human-directed/coached, never an
  autonomous trigger.
- Reimagined from the raw material at `knowledge/strategies/toll-and-defense-math.md`
  (CARRY-WITH-CHANGES; re-rooted in the reborn vision — priority ranks/orders, guards +
  scoring + coaching, no autonomous driving).
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
