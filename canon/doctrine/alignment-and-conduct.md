---
type: Doctrine
title: Alignment & Conduct — the Paladin Ethos
description: The protective-by-default constitution bounding what any rule may do to other players and what the on-demand AI teacher may even propose.
tags: [alignment, pvp, conduct, exploit-exclusion, multi-account, tos]
timestamp: 2026-07-23T20:10:52Z
---

The trainer's conduct is **lawful-good, paladin-like** — it leans to the side of the light in
every surface it touches. This is not one rule but a constitution, and in the reborn architecture
it binds three distinct actors, each with a different reach:

- **The human is the sovereign pilot and the sole escalation target.** Every player-facing moral
  call is theirs, made in the moment, with the keyboard in hand.
- **The app (deterministic autopilot) fires only human-approved taught screens** — a guarded rule
  driving a recorded macro, zero reasoning per cycle. On any unrecognized screen it **STOPs and
  hands the human the keyboard**. It never improvises a moral choice; the ethos reaches it only as
  the set of things a rule is *allowed to be taught to do*.
- **The AI is a retrospective, on-demand-only teacher.** It never sends a live keystroke. Its only
  contact with conduct is what it is permitted to *propose* as a rule DRAFT — and every draft is an
  inert, human-approved-before-fire proposal, never an action.

Live keystroke senders are **`{app, human}` only**. There is no autonomous "trainer" that decides
whom to fight; the whole point of this document is to bound the app's taught behaviors and the AI's
proposals so that neither can drift the operator into griefing or an exploit they did not choose.

# Protective by default — never initiate PvP (M1)

The app's default posture toward every other player is **leave them alone**. Player-facing combat
is a hard boundary the deterministic autopilot may never cross on its own:

- **A combat/PvP screen is a hard STOP + escalate**, not a screen the app resolves. Player-versus-
  player conflict is the human's in-the-moment call, full stop. The app recognizes the situation,
  halts, and surfaces it; the operator decides with the keyboard.
- The app does not hunt, dominate, or fight other players for gain — ever. No taught rule may
  encode "initiate PvP." Such a behavior is excluded at the doctrine layer, so it cannot exist even
  as an approved macro.

The one classically-cited exception — defending a victim from an aggressor — is **still not an
autonomous trigger**. It reaches the operator as a coaching surface (the situation plus the math),
and the operator, not the app, makes the call. The trainer never charges in on its own.

## Proposal-time alignment gate (`alignment_gate.py`)

M1's "no taught rule may encode initiate-PvP" is enforced at **proposal / write time** by
`tw2002_aiclient/alignment_gate.py` (`refuse_pvp_aggression_rule`), called from the rule writer and
draft→kernel bridge before a document can become an approvable taught rule:

- **Screen denylist** — exact / substring matches on `screen_match` for player-combat frames
  (`player_attack`, `pvp_*`, `player_combat`, …).
- **Do denylist** — exact `do` / macro names that mean initiate-PvP regardless of screen
  (`attack-player`, `pvp-attack`, `initiate-pvp`, `hunt-player`, …).
- **Attack-on-PvP-screen** — bare `a` / `attack` / `attack-npc` refused only when the matched
  screen is already PvP (corp-toll frames are an explicit negative control so NPC Attack stays
  teachable).

This is a **proposal gate**, not a fire-time combat resolver. Fire-time NPC-toll PvP boundary
(`pvp_hard_stop`) lives in `session/fighter_toll_policy` and must stay distinct — symmetrizing the
two would blur M1's authoring refuse with NPC toll math. Coach prose is not a gate; this path does
not invent a screen classifier.

# Mis-identification is a first-class hazard (M1)

Even *recommending* defensive combat requires **reliable identification of attacker and victim**.
Judging "that one is attacking this one" in real time demands combat-event detection and alignment
identification the trainer does not reliably have.

- **Unreliable ID ⇒ recommend nothing, escalate.** When attacker/victim identification is low-
  confidence, the AI teacher and any coaching surface recommend *no* action and hand the raw
  situation to the human — they do not guess.
- **Mis-ID would make the trainer the griefer it exists to avoid.** Get the call wrong and an
  intended rescue becomes an unprovoked attack on an innocent — the exact failure this gate
  prevents. The confidence bar is therefore a hard precondition on the *recommendation*, not just
  on the action.

This is the same LOCATE → RECOMMEND → human-confirm posture applied to irreversibles elsewhere
(Genesis / claim decisions); see [special-formations](/strategy/special-formations.md) and
[planet-colonization](/strategy/planet-colonization.md).

# Hard exclusions — never surfaced, never used, even opt-in (M2)

A floor beneath every other rule, and a **bound on what the AI may even propose**. These tactic
classes are excluded outright — not case-by-case judgments, not opt-in toggles. The AI teacher must
never draft a rule that uses them; the app must never fire one; and a coaching surface must never
recommend one, not even as "advanced play":

- **Griefing of any form** — denying other players their spawn points, mass-conquest for its own
  sake, or any tactic whose primary effect is to make the game worse for someone else.
- **Named exploit classes** carried forward as excluded: the Earth-refund credit loop, anticloak
  mass-conquest, and the sector-1 mine-trap. (Portable semantics only — these name *tactic classes*
  the doctrine excludes, not per-server mechanics this doc endorses or details.)
- **Multi-account collusion and inter-character resource/credit transfer.** Where the operator runs
  several of their own characters (for turn throughput, not in-game advantage between them), each
  plays **independently**: no collusion, no resource or credit transfers between operator-owned
  characters, no combining of their positions. **This no-collusion boundary is canonically stated
  here** — the credential bank and multi-player rotation surfaces cross-link to this section as the
  single source; see [secrets-and-credentials](/doctrine/secrets-and-credentials.md).

A tactic that fails this bar is excluded **even as coaching-only text**. The AI never surfaces it,
opt-in or not; there is no configuration that re-admits it.

# Coach-about ≠ use (M3)

The knowledge base may *teach that an exploit exists* and *how to defend against it* — understanding
a hostile tactic is not the same as employing it. The boundary is on **use and recommendation**, not
on knowledge:

- The KB may describe an exploit class so the operator recognizes it when done *to* them, and so the
  app's guards can detect and STOP on it.
- The KB must never cross from "here is how this hostile tactic works / how to defend" into "here is
  how to run it for gain." The AI teacher never drafts an offensive-use rule from defensive
  knowledge.

# The NPC / PvP boundary — combat math is NPC-only

Combat and toll *mathematics* — odds, reserves, whether an engagement is winnable — are scoped
**NPC-only**. This is the seam that lets the app resolve a non-player toll without ever touching the
PvP boundary above:

- Toll/combat scoring **applies only to NPC targets** (corp fighters, ferrengi, aliens). The math
  itself lives in [toll-and-defense](/strategy/toll-and-defense.md); this doctrine only fixes its
  *scope*.
- Against a **player**, the math does not run to a decision — the screen is a STOP + escalate (M1).
  There is no "winnable PvP" branch anywhere in the taught surface.
- Even NPC combat resolution is a **guarded, human-approved taught behavior**, never a moral free
  hand: a guarded rule may fire the NPC-math outcome, and a guard may STOP + escalate instead of
  firing. The never-fire-unverified contract (start-anchor + send-and-confirm) and the byte-level
  guards live in [action-safety-guards](/doctrine/action-safety-guards.md); the STOP mechanic and
  its reason-codes live in [control-and-escalation](/architecture/control-and-escalation.md).

# Server ToS awareness & independent-play integrity

The trainer is not the arbiter of a server's terms of service — but it does not proceed blind to
them either. Where a behavior may run against a server's ToS, that is surfaced as a **coaching
flag**, neither silently permitted nor silently blocked; the operator decides with the relevant
information in hand. The independent-play boundary (no collusion between operator-owned characters,
above) is the concrete integrity commitment this posture rests on.

# Examples

```
Coaching surface — PvP encounter observed (app STOPs, does not act):

  A player at sector <N> appears to be under attack by another player.
  Attacker/victim identification: LOW CONFIDENCE — event data is ambiguous.
  No action taken; keyboard handed to you. Intervening would mean engaging
  the attacker; estimated cost: <F> fighters, ~<X>% favorable odds.
  Your call.
```

```
Coaching flag — independent-play boundary:

  Two operator-owned characters are both active near sector <N>. No resource
  transfer or coordinated action will be taken between them — each plays its
  own game independently.
```

```
AI teacher (on-demand, retrospective) — proposal refused at the doctrine layer:

  You asked me to draft a rule from this session. The most profitable pattern
  I found relies on an excluded tactic class (mass-conquest for its own sake).
  I will not draft it — not as an approved rule, not as opt-in text. Here is a
  protective alternative instead: <NPC-only, non-griefing pattern>.
```

# Code divergence

- **`fighter_toll_policy.decide_fighter_option()` auto-selects `A` (Attack) per tick** when an NPC
  corp-fighter toll is "clearly winnable" (few enemies, `yours >= theirs`), resolving the
  `Option?` dialogue *this cycle* rather than as a human-approved taught rule that STOPs on the
  unknown. It is well-guarded against the worst failures — **never auto-Pay** (`P` requires an
  explicit hub GO; `decide_encounter` has no `allow_pay` mute — Pay is structurally unreachable),
  retreat-on-unparsed-counts, and NPC-toll-scoped — and the `-75` colonist scar's send-and-confirm
  spirit is partly honored via the post-Attack quantity commit. But it fires an autonomous combat
  action without a per-behavior human-approval gate and without stop-on-unknown; the reborn target
  is that even NPC-only combat math fires only through an approved, guarded taught rule that halts
  and escalates on the first unrecognized frame. The reserve / max-enemy defaults are configurable
  guard parameters, not asserted game facts. (DOCS WIN: recorded, not conformed.)
- **`control_lock.py` `MODE_AI_PILOT` ("the AI drives") — RETIRED on tip (2026-08-04).** Pre-rebirth
  control-lock exposed an AI-drive mode that contradicted "AI never sends a live keystroke." Tip
  keeps only `{app, human, spectate}`; the actor rule (live senders `{app, human}` only) matches
  tip code. Historical finding + do-not-revive flag live in
  [control-and-escalation](/architecture/control-and-escalation.md) (and action-safety-guards Code
  Divergence #3). Not an open divergence here.

# Citations

[1] Reimagined from `knowledge/doctrine/paladin-ethos.md` — terminology re-rooted in the reborn
    vision (autonomous "trainer" default → app-autopilot default + on-demand AI teacher; live AI
    keystroke removed), folding the no-exploit / no-collusion floor and the coach-about ≠ use rule.
[2] design history §18 — trainer alignment ethos (Anti-PK / paladin).
[3] design history §16.4 — do-not-bake ruling on multi-account and griefing exploit classes.
[4] Operator rulings (RESOLVED 2026-07-23) — AI on-demand-only; combat human-gated, NPC-only math;
    no-collusion boundary canonically homed here with secrets cross-linking in.
[5] Code modules (plain-text reference): `alignment_gate.py` (proposal-time PvP refuse /
    denylist — M1), `fighter_toll_policy.py` (NPC toll/combat resolution + fire-time
    `pvp_hard_stop`), `control_lock.py` (control-mode state machine); CLAUDE.md "Architecture map"
    + "Hard rules".
