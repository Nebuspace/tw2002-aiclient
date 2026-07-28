---
type: System
title: The Guarded Rule–Macro Engine (the reflex layer)
description: The deterministic single-cycle decision unit the app plays — `when(screen_match + guards) → do(macro)`, prioritized and scoped — firing only on taught screens, never guessing, and never running a line of AI reasoning per cycle.
tags: [architecture, autopilot, rules, macros, guards, determinism, human-in-the-loop]
timestamp: 2026-07-23T20:11:59Z
---

The reflex layer is the deterministic decision unit the **App** plays: a settled screen comes in,
the engine looks it up against a set of **guarded, prioritized rules**, and — if exactly one
recognized-and-safe rule wins — it plays that rule's macro. If nothing matches, or the winning
rule's guards refuse, it does not guess: it defers to
[the escalate-on-unknown handoff](/architecture/control-and-escalation.md) and hands the keyboard
to the human. There is **zero AI reasoning per cycle** — recognition and playback are mechanical
lookups, not inference, not scoring, not goal-seeking.

This concept owns the **single-cycle decision only**: one settled screen → one macro (or one STOP).
The *multi-cycle run-loop* that repeats this decision across many screens of a taught behavior —
re-classifying every cycle, stopping on the unknown mid-run, arming only on human confirm — is
owned by [the APP Autopilot Model](/architecture/app-autopilot-model.md); this concept cross-links
it and does not restate it. The `do` target's capture-and-replay mechanics belong to
[Macros](/engine/macros.md); the screen read feeding `when` belongs to
[Screen Understanding](/engine/screen-understanding.md); the numeric `priority` values and the
strategic "which taught behavior to prefer" ordering belong to
[the Priority Engine](/engine/priority-engine.md).

# The Rule

A rule is the atomic reflex: **`when(screen_match + guards) → do(macro)`**, carrying a `priority`
and a `scope`. Every field is deterministic and human-inspectable — a rule contains no model, no
prompt, no free-form reasoning.

## `when` — the recognition half

- **`screen_match`** — the anchor that says "this rule is *for* this screen." It is a screen-class
  identifier (`main_command`, `port_trade`, `sector_display`, a login state, …) or a menu-signature
  hash, produced by [Screen Understanding](/engine/screen-understanding.md) from the settled render.
  A rule fires only when the *current* settled screen classifies to the rule's `screen_match`. This
  is the literal boundary between "known → fire the taught rule" and "unknown → STOP + hand off":
  no `screen_match` in the rule set matches the screen ⇒ escalate.
- **`guards`** — a list of **typed predicates** over facts read by
  [Screen Understanding](/engine/screen-understanding.md) and the
  [World Model](/engine/world-model.md): fighter counts, credits balance, cargo/stock levels,
  a port's class or last-seen prices, **and the staleness of each of those facts**. Guards are
  boolean and deterministic. A guard is not a scorer — it does not rank the rule, it only decides
  whether the rule is *allowed to fire at all*. Every guard must pass for the rule to be eligible;
  any guard that fails removes the rule from contention.

**Unknown is a first-class guard input.** When a fact a guard needs cannot be read — credits
unparseable, fighters `?`, a world-model record too old to trust — the fact is *unknown*, not zero
and not a guess. A guard over an unknown fact **fails closed**: it does not fire on a fabricated
value. This is why "credits unknown / credits stale / fighters unknown / fighters stale" are STOP
reason codes rather than silent defaults (see the
[escalation reason-code catalog](/architecture/control-and-escalation.md)).

## `do` — the action half

`do` names a **macro**: a taught keystroke sequence captured from human demonstration and replayed
deterministically, with all of its own replay-safety machinery (start-anchor, send-and-confirm,
halt-on-divergence) as specified in [Macros](/engine/macros.md). The engine never composes a novel
action; it plays a named, already-recorded, already-approved macro or it plays nothing.

## `priority` and `scope`

- **`priority`** — an integer; **higher dominates**. When more than one rule matches the screen and
  passes its guards, the engine fires the single highest-priority rule. The concrete priority
  numbers and their rationale are the [Priority Engine](/engine/priority-engine.md)'s domain — this
  concept only specifies that priority is an integer total order used to pick one winner.
- **`scope`** — `one-shot | repeating`. A `one-shot` rule fires once for its triggering screen; a
  `repeating` rule is eligible again on every recurrence of its screen. The *run-loop* safety
  contract for a `repeating` macro — human-armed before it can run, stop-on-unknown mid-run,
  guard-STOP-not-rotate — is owned by [the APP Autopilot Model](/architecture/app-autopilot-model.md)
  and is not restated here.

# The Reflex Loop (one cycle)

```
settled screen
  → classify → screen_match
  → collect rules whose screen_match == this class      (recognition)
  → drop any rule with a failing guard                  (safety filter, fail-closed on unknown)
  → of the survivors, is there a rule whose guard says STOP?  → STOP + escalate (do not fire)
  → else pick the single highest-priority survivor      (deterministic tie-break by priority int)
  → play its macro                                      (deterministic replay, halt-on-divergence)
  → no survivors at all → defer to escalate-on-unknown  → hand keyboard to human
```

Two properties are load-bearing:

1. **Zero AI reasoning per cycle.** Every step above is a lookup, a boolean filter, or an integer
   comparison. Nothing on this path calls a model, computes an expected value, or picks an action
   by scoring competing goals. The AI is a *retrospective author* of rules
   ([the AI Teacher](/engine/ai-teacher.md)), never a participant in a live cycle.
2. **Recognition gates everything.** If the screen does not classify to a rule the set already
   holds, the loop produces a STOP, not a default. The engine has no fallback action, no
   "best-guess" branch, no retry-with-a-different-key. Not-recognized ⇒ hand off.

# The Human-Approval-Before-Fire Gate

**Every rule that can fire is human-approved first.** This holds identically whether the rule was
recorded directly by the human (capturing their own keystrokes at an escalation) or authored by
[the AI Teacher](/engine/ai-teacher.md) via a human-invoked Analyze. Authorship and approval are
always separate steps, and the human holds the second one exclusively.

An **unapproved rule is an inert draft**: it lives in the rule store, it can be viewed and edited,
but the reflex loop **never considers it** — it is not in the set the "collect matching rules" step
draws from. A draft has no priority standing, cannot win a tie, and cannot fire. Approval is the
one transition that moves a rule from inert-draft into the live, fireable set. Nothing the AI writes
drives a keystroke autonomously; nothing a miner proposes fires until a human approves it.

# Guards That STOP Rather Than Fire

A guard is not only a permission filter — a guard may **actively STOP and escalate** instead of
letting its rule fire. This is the reflex-layer expression of "the app may choose to hand off rather
than act." The canonical STOP-causing guard families:

- **Depletion** — a resource the macro consumes is exhausted or below a safe floor (turns spent,
  cargo empty, credits below a working-capital reserve). The guard STOPs; it does **not**
  autonomously rotate to a different source or a different macro. (Rotation is a strategic decision;
  in the reborn model it is the human's to make — see
  [the APP Autopilot Model](/architecture/app-autopilot-model.md)'s guard-STOP-not-rotate rule.)
- **Hazard** — the screen or state carries a risk the taught rule must not auto-answer: a
  session-boundary / game-select screen, an unverified destructive prompt, a combat/PvP situation.
  Combat is **human-gated**; the reflex layer never initiates PvP, and hostile-math autopilot is
  NPC-only. The guard STOPs and escalates.
- **Desync / staleness** — a guard fact is unknown or too stale to trust (credits unknown, fighters
  stale). Fail-closed: STOP rather than act on a value that might be wrong.

A STOP carries a **typed reason code** (not free text), drawn from the fixed catalog specified in
[Control & Escalation](/architecture/control-and-escalation.md); the human-facing banner renders the
code's label. A guard that STOPs is doing its job — a refusal to fire is a first-class, correct
outcome of the reflex loop, exactly as much as a successful macro play is.

# Built-In Guarded Rules (reference archetypes)

The engine ships a small number of built-in guarded rules that are, structurally, exactly the
`when + guards → do` shape above — they are the reference archetypes new taught rules imitate. They
are deterministic (no LLM) and each embodies the fail-closed / STOP-not-guess discipline.

- **Auto-haggle** — matches the port **OFFER** sub-dialogue and plays a deterministic no-LLM
  counter-offer negotiation. It is **on by default, as a guarded rule** (operator ruling
  2026-07-23): "on by default" is not "unguarded." Its mandatory guards are a **fresh-render
  pre-send gate** (the counter-offer is computed off a *freshly re-read* screen, never a stale or
  transitional render) and a **`DESYNC_FALLBACK`** posture (on any desync — a bare `Command [TL=…]`
  where the offer prompt should be, an unconfirmed acceptance — it accepts the shown default / backs
  out conservatively and reports `resolved=False`, never a guessed price). Full behavior lives in
  [Auto-Haggle](/engine/auto-haggle.md) and the guard contract in
  [Action-Safety Guards](/doctrine/action-safety-guards.md).
- **Fighter-toll** — matches a fighter-toll / `Option?` prompt and resolves it against a reserve
  policy. It **never** presses `P` (pay the toll) blind and never sends an unparsed option; an
  ambiguous or unaffordable toll resolves to a **safe retreat**, and when the reserve math cannot be
  satisfied the guard **holds rather than fights**. It is the archetype of a guard that answers a
  hazardous prompt only within a safe, deterministic envelope and STOPs otherwise.

# Boundary

| this concept owns | this concept defers |
|---|---|
| the single-cycle decision: one settled screen → one macro or one STOP | the multi-cycle run-loop that repeats it → [app-autopilot-model](/architecture/app-autopilot-model.md) |
| the rule schema (`when`/`guards`/`do`/`priority`/`scope`) and the reflex-loop lookup | macro capture & deterministic replay internals → [macros](/engine/macros.md) |
| guard evaluation (typed predicates, fail-closed on unknown, STOP-vs-fire) | the STOP → keyboard handoff mechanics & reason-code catalog → [control-and-escalation](/architecture/control-and-escalation.md) |
| that `priority` is an integer total order picking one winner | the concrete priority numbers & strategic behavior ordering → [priority-engine](/engine/priority-engine.md) |
| that `screen_match` is the recognition anchor | how a screen becomes a class / signature → [screen-understanding](/engine/screen-understanding.md) |
| that guards read parsed-state / world-model facts + staleness | the guard-authoring safety rails (arm-confirm, novelty-halt) → [action-safety-guards](/doctrine/action-safety-guards.md) |

# Schema

A rule (conceptual — the reborn target schema, not the current on-disk skill shape; see
Code Divergence):

| field | type | meaning |
|---|---|---|
| `screen_match` | screen-class id or menu-signature hash | the recognition anchor; the rule is eligible only when the settled screen classifies to this |
| `guards` | list of typed predicates | boolean facts over parsed-state / world-model (fighters, credits, stock, port class/prices) **and their staleness**; all must pass; fail-closed on unknown; any may instead STOP + escalate |
| `do` | named macro | the taught, human-approved keystroke sequence played on a win |
| `priority` | int (higher dominates) | total order used to pick one winner when several rules match and pass |
| `scope` | `one-shot` \| `repeating` | fire-once vs eligible-on-every-recurrence (run-loop safety of `repeating` owned by app-autopilot-model) |
| `approved` | bool | inert **draft** until a human approves; the reflex loop only ever considers `approved` rules |

Reflex-loop outcomes for one settled screen:

| situation | outcome |
|---|---|
| ≥1 approved rule matches, guards pass, no STOP-guard | fire the single highest-`priority` survivor's macro |
| survivor's guard says STOP (depletion / hazard / desync) | **STOP + escalate** with a typed reason code — do not fire |
| no approved rule's `screen_match` matches the screen | **STOP + escalate** (escalate-on-unknown) — hand keyboard to human |
| only draft (unapproved) rules match | treated as no match ⇒ STOP + escalate (drafts never fire) |

# Examples

A guarded rule firing on a recognized screen:

```
1. Settled screen classifies to `port_trade` (an OFFER sub-dialogue).
2. Engine collects approved rules whose screen_match == the offer prompt: the built-in auto-haggle.
3. Guards: fresh-render pre-send gate PASSES (the offer line was just re-read). No desync.
4. One survivor, highest (only) priority → play the auto-haggle macro (deterministic counter-offer).
5. Result settles; the run-loop (app-autopilot-model) re-reads and takes the next cycle.
```

A guard STOPping instead of firing:

```
1. Settled screen classifies to `port_trade`. An approved trade-macro rule matches.
2. Guard reads credits from the world-model → the value is STALE (too old to trust).
3. Guard fails closed and raises STOP with reason code `credits_stale`.
4. Engine does NOT fire the macro. It hands the keyboard to the human with the STOP banner.
```

An unrecognized screen (escalate-on-unknown):

```
1. Settled screen classifies to a class no approved rule holds a screen_match for.
2. "Collect matching rules" returns empty. No default, no retry, no best-guess key.
3. Engine STOPs with reason `autopilot_no_candidates` and hands off to the human — the
   escalation moment where the human may Respond, Record a macro, or ask the AI to Analyze.
```

# Code Divergence

The reborn reflex layer described above **does not yet exist as a module**. There is no code that
composes `screen_match` + `guards` + a named macro into a prioritized, scoped, human-approved rule
and runs the lookup-only reflex loop. This is the single biggest missing subsystem of the reborn
architecture, recorded here (DOCS WIN) rather than reconciled away.

- **Per-cycle EV scoring vs. lookup-only reflex.** `twclient/autopilot.py`'s `select()` is a
  *continuous cost-benefit scorer*: each tick it re-scores every candidate action (`_score_chain` /
  `_score_upgrade` / `_score_explore`), ranks them by `ev_per_turn`, and picks the highest —
  optionally overridden by `priority_engine.recommend_actions()` (RT-aware / link-count focus). This
  is exactly the **per-cycle expected-value action-picker** the reborn model retires: it *reasons*
  about what to do each cycle instead of *recognizing a taught screen and playing its macro*, and it
  can choose a live action on a screen no human ever taught. Under this canon the per-cycle EV select
  is a divergence, not a carry. (The *run-loop* half of the same divergence — the ASSESS→SELECT→
  EXECUTE→RECORD tick loop that drives it — is dispositioned in
  [the APP Autopilot Model](/architecture/app-autopilot-model.md); this concept records the
  single-cycle "score-and-pick vs. lookup-and-play" divergence.)
- **`priority_engine.py` is a strategic ranker, not a reflex.** `recommend_actions()` ranks `run_chain` / `upgrade` / `explore` by cr/turn with round-trip and
  link-count gating. In the reborn model that ranking informs *which taught behavior a human prefers*
  ([Priority Engine](/engine/priority-engine.md)); it must **not** be wired as the live per-cycle
  action-picker that lets a computed EV win over an unrecognized screen. Its current role as a
  `select()` override is part of the same per-cycle-scoring divergence above.
- **No `guards` / `priority` / `scope` / `approved` fields on the stored unit.**
  `twclient/skills.py`'s `save_skill()` persists `{steps, source, mined_stats, start_anchor}` — it
  carries the macro and its start-anchor replay-safety, but there is no `screen_match`, no typed
  `guards`, no `priority` integer, no `scope`, and no `approved` flag. The rule schema in this
  concept is a target the skill store must grow into; today a "rule" is effectively just a macro plus
  a start-anchor.
- **Auto-haggle money-path finding (verified 78-turn misfire).** The auto-haggle archetype has a
  recorded real-world misfire in which a counter-offer computed off a **stale / transitional render**
  produced a wrong result; the fresh-render pre-send gate and `DESYNC_FALLBACK` hardening in
  `twclient/haggle.py` exist precisely to close it, and per operator ruling 2026-07-23 those guards
  are **mandatory** for shipping auto-haggle on-by-default. Recorded here as a money-path finding so
  the archetype is never treated as an unguarded default.

These are documentation-only findings — this concept edits no code. The reflex engine, the rule
schema fields, and the retirement of the per-cycle EV picker are separate future work orders.

# Citations

[1] twclient/autopilot.py (per-cycle EV `select()` scorer + `priority_engine` override — the retired live action-picker)
[2] twclient/priority_engine.py (`recommend_actions()` strategic ranker — informs behavior ordering, not a live per-cycle picker)
[3] twclient/skills.py (macro store: `start_anchor` + steps; no guards/priority/scope/approved fields yet)
[4] twclient/classify.py (screen classification anchors feeding `screen_match`)
[5] twclient/state_parser.py (best-effort guard facts — credits/fighters/sector — LAST-match anchored, unknown-first-class)
[6] twclient/haggle.py (auto-haggle archetype: fresh-render pre-send gate + `DESYNC_FALLBACK`; the money-path misfire hardening)
[7] twclient/fighter_toll_policy.py (fighter-toll archetype: reserve policy, safe-retreat, never blind-pay)
[8] canon/log.md 2026-07-23 (operator ruling: auto-haggle on-by-default as a guarded rule with mandatory hardening)
