---
type: Reference
title: Explore Defensive Posture (pre-uncharted gate)
description: Pure decision module that gates map-fill explore behind a StarDock fighter-dealer detour when the ship is under a judgment fighter floor — recommends seek/halt only; never sends keystrokes or spends credits.
tags: [strategy, exploration, defense, judgment-defaults, human-gated-purchase, fail-closed]
timestamp: 2026-08-08T02:50:00Z
---

Map-fill explore pushes the ship into **uncharted** warps. Before that commitment, tip code can
ask a narrow policy question: *are we carrying enough fighters that wandering unknown sectors is
a deliberate risk rather than an accidental naked run?* The answer lives in
`tw2002_aiclient/session/explore_defensive_posture.py` — a **pure decision** module. It does not
send keystrokes, open a purchase dialogue, or spend credits. Explore (and related priority /
world-model callers) wire the verdict: route toward a known StarDock fighter dealer within a
turn budget, then **halt** with a named reason so a human-approved (or follow-up taught) purchase
can happen. Unreachable / scarce / unknown inputs degrade to today's explore — no new stall
hunting a dealer that may not exist.

This concept documents that gate and its five **judgment defaults**. They are live tip constants,
not Max-ratified operational numbers. Escalate only if Max wants different defaults. They are
**not** a reintroduction of the stripped toll/combat `keep_min_defense_fighters` / defense-floor
math retired in [Toll & Defense Math](/strategy/toll-and-defense.md) (Option B, 2026-08-05) —
same archive ancestry, different consumer and semantic (pre-uncharted explore gate vs NPC toll
auto-Attack clamps).

Cross-links: the explore intents and stop-on-unknown invariant live in
[Frontier Exploration Policy](/strategy/exploration-policy.md); purchase remains human-gated per
[Ship Progression](/strategy/ship-progression.md) and
[control-and-escalation](/architecture/control-and-escalation.md).

# Scope

| In scope | Out of scope |
|---|---|
| Pre-uncharted **map-fill** posture check | Live keystroke send / credit spend |
| StarDock-landmark dealer hop budget | PvP or NPC toll combat math |
| Fail-closed skips when inputs unknown | Replacing Play explore flags / intents |
| Halt reason `halt_defensive_posture` for human/taught buy | Autonomously completing a fighter purchase |

# Schema — the five policy constants (judgment defaults)

Every row is a tip default in `session/explore_defensive_posture.py`. Treat as configurable
judgment, not ratified canon numbers. Cite the constant assignment line, not only the docstring.

| Constant | Tip default | file:line | Meaning |
|---|---|---|---|
| `FIGHTER_FLOOR` | `20` | `session/explore_defensive_posture.py:53` | Minimum fighters aboard before uncharted map-fill may proceed without a dealer detour. Aligns with archive `EconCaps.keep_min_defense_fighters`; stock starts are often ~6. **Distinct from** the stripped toll-defense combat floor — do not coach this as auto-Attack math. |
| `CREDIT_FRACTION_CEILING` | `0.10` (10%) | `session/explore_defensive_posture.py:56` | Cap on how much of **known** credits may be committed to the defensive stack (e.g. 100k start → ≤10k). |
| `FIGHTER_UNIT_PRICE_DEFAULT` | `100` cr/fighter | `session/explore_defensive_posture.py:59` | Placeholder Class-0 / StarDock unit price until a live quote is introspected (archive `FIGHTER_UNIT_PRICE_CLASS0`). |
| `DEALER_DETOUR_TURN_CEILING` | `20` turns one-way | `session/explore_defensive_posture.py:62` | Hop/turn budget for routing to a known StarDock before giving up and exploring as today. |
| `CASH_FLOOR_AFTER` | `10_000` cr | `session/explore_defensive_posture.py:65` | Credits that must remain after the planned spend (archive `EconCaps.cash_floor`). |

Related (not a sixth policy number): halt reason string `HALT_DEFENSIVE_POSTURE` =
`"halt_defensive_posture"` at `session/explore_defensive_posture.py:69` — explore surfaces this when
the dealer is reached (or already underfoot) while still under the fighter floor so purchase stays
human-gated / follow-up-taught.

# Mechanism — `decide_defensive_posture` (pure)

`decide_defensive_posture(...)` (`session/explore_defensive_posture.py:118`) returns a frozen
`DefensivePostureDecision` with `action` ∈ `{seek_dealer, already_sufficient, skip_*}`:

1. **Unknown fighters** → `skip_unknown_fighters` (fail-closed; explore as today).
2. **Fighters ≥ floor** → `already_sufficient` (no detour).
3. **Unknown credits** → `skip_unknown_credits`.
4. **No known StarDock path** (`hops_to_dealer is None`) → `skip_unreachable` (no dealer hunt).
5. **Detour too far** (hops > `DEALER_DETOUR_TURN_CEILING`, or turns remaining < hops) →
   `skip_scarce_turns`.
6. **Cannot afford** a positive qty under fraction ceiling ∧ cash floor ∧ unit price →
   `skip_cannot_afford`.
7. Else → `seek_dealer` with recommended `qty` and `stack_cost` (still not a send).

StarDock hop helper: `hops_to_stardock` (`session/explore_defensive_posture.py:87`) — shortest
known-graph hops to a `STARDOCK_LANDMARK`, or `None` if unknown.

# Verification status

**JUDGMENT DEFAULTS — not Max-ratified.** The module docstring states the contract explicitly
(`session/explore_defensive_posture.py:12–23`): document the numbers; escalate only if Max wants
different defaults. Do not promote these into toll/combat operational math without a separate
ruling. Live wiring into explore / priority / world-model is tip reality; this concept is the
missing canon coverage for that wiring.

# Citations

- Tip module `tw2002_aiclient/session/explore_defensive_posture.py` — constants `:53`–`:65`, halt
  reason `:69`, `decide_defensive_posture` `:118`
- Sibling explore policy — [exploration-policy](/strategy/exploration-policy.md)
- Stripped combat-floor note (do not conflate) — [toll-and-defense](/strategy/toll-and-defense.md)
  § Schema (Option B strip of `keep_min_defense_fighters`)
- Purchase / human-approval boundary — [ship-progression](/strategy/ship-progression.md) ·
  [control-and-escalation](/architecture/control-and-escalation.md)
- Origin WO — `workorders/WO-CANON-DRAFT-EXPLORE-DEFENSIVE-POSTURE-COVERAGE.md` · 6-lens aiclient
  audit 2026-08-08T02:12Z
