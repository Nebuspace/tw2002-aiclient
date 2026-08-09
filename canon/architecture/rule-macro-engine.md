---
type: System
title: The Guarded Rule–Macro Engine (the reflex layer)
description: The deterministic single-cycle decision unit the app plays — `when(screen_match + guards) → do(macro)`, prioritized and scoped — firing only on taught screens, never guessing, and never running a line of AI reasoning per cycle.
tags: [architecture, autopilot, rules, macros, guards, determinism, human-in-the-loop]
timestamp: 2026-08-06T02:39:00Z
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

## Draft stub → kernel document bridge (no invented defaults)

Analyze / teach overlays produce a **pre-kernel draft stub** whose vocabulary is deliberately
disjoint from the fireable kernel rule schema:

| Stub (pre-kernel) | Kernel (fireable) |
|---|---|
| `when` / `do` / `source` / `playback_eligible` | `rule_id` / `screen_match` / `do` / `priority` (+ `guards` / `scope` / `approved`) |

The kernel parser rejects unknown fields, so stub-only keys (`source`, `playback_eligible`) cannot
ride along. Conversely, a stub has **no** `rule_id` or `priority` — those are human decisions, not
teacher observations.

`tw2002_aiclient/cockpit/draft_approve.py::bridge_to_kernel_document` is the one crossing. It is a
**pure translation** (no filesystem, no approval side-effect) and it **refuses rather than invents**:

- What the teacher observed (e.g. screen class → `screen_match`) may be carried across.
- What only a human can decide — *what to call this* (`rule_id`), *what it does* (`do`), *how it
  ranks* (`priority`), *scope* — must be supplied as explicit arguments; absence is a hard refuse,
  never a defaulted value.

That asymmetry is **Max's ruling of 2026-07-29: no invented defaults** (logged in
[DECISIONS](/DECISIONS.md)). A minted default `priority` is the named worst failure mode: every
AI-authored rule would arrive at the same rank, and the kernel STOPs on a tie
(`autopilot_ambiguous_rules`) rather than guessing — so a default would convert "the teacher
proposed something" into "the autopilot halts" exactly when the library became useful. Tip identity
collection (`create_identity_session` / `HUMAN_SUPPLIED_FIELDS`) enforces the same refuse-not-default
posture on empty fields.

Cockpit approve → bridge → `rules.writer` promote remains the only path from inert draft to
`approved: True`. The bridge never arms and never sends.

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

**Tip honesty (2026-08-05 · `WO-CANON-FIX-RULE-MACRO-ENGINE-STALE-DIVERGENCE`):** the reborn
reflex layer **ships**. Claiming it "does not yet exist" was stale — do not reintroduce that
wording. Live homes:

| Piece | Tip home |
|---|---|
| Lookup-only kernel (`screen_match` + `guards` + `priority` + `scope` + `approved` → macro or typed STOP) | `tw2002_aiclient/rule_engine.py` (`select_rule`, `Rule` / `Guard` / `Decision`) |
| Persist / approve / CLI | `tw2002_aiclient/rules/store.py`, `writer.py`, `cli.py` (`rule approve` is the only path to `approved: True`) |
| Draft stub → kernel bridge (refuse, never invent `rule_id`/`priority`) | `tw2002_aiclient/cockpit/draft_approve.py` (`bridge_to_kernel_document`, Max 2026-07-29) |
| Live propose (classification + facts → `Decision`) | `tw2002_aiclient/rules/reflex.py` (`propose_macro`); called from `session/protocol.py` |
| Human arm before bytes move | `tw2002_aiclient/rules/arm.py` + taught run path (`arm-confirm` → autoloop → `loops.player.replay_loop`) |

A `Decision` naming a macro is still a **proposal** — selecting does not bypass
`NEVER_AUTO_ACTION_CLASSES` or the human arm-confirm rail (see `rules/reflex.py` module docstring).

Honest residuals (not "engine missing"):

- **Per-cycle EV action-picker is retired from the live driver.** Archive
  `archive/pre-rebirth-2026-07-23/twclient/autopilot.py` still shows the old
  score-every-tick `select()` / `_score_chain` pattern. Product tip must not re-wire that as the
  live chooser on an unrecognized screen. Strategic EV *display* (e.g. cockpit FOCUS /
  `focus_status.py` ranking) may still surface `ev_per_turn` for the human — that is a ranker /
  coach surface, not the reflex loop.
- **`priority_engine` remains a strategic ranker, not a reflex.**
  `recommend_actions()` informs which taught behavior a human prefers
  ([Priority Engine](/engine/priority-engine.md)); it must **not** override `select_rule` so a
  computed EV wins over `autopilot_no_candidates`.
- **Auto-haggle money-path finding (verified 78-turn misfire).** Stale/transitional-render
  counter-offer misfire; fresh-render pre-send gate + `DESYNC_FALLBACK` hardening remain
  **mandatory** for on-by-default auto-haggle (operator ruling 2026-07-23). Tip live port is
  `tw2002_aiclient/session/haggle.py` (params via `haggle_params.py` / `data/haggle/params.json`);
  archive `twclient/haggle.py` is port-source only. The finding stands on tip.

This section records tip↔prose honesty. Product WOs for remaining residuals (EV display vs driver
discipline, auto-haggle default arming, AI-teacher draft author) are separate queue rows — not a
rebuild of the kernel.

# Citations

[1] `tw2002_aiclient/rule_engine.py` (lookup-only `select_rule` kernel — shipped)
[2] `tw2002_aiclient/rules/reflex.py` / `store.py` / `writer.py` / `cli.py` / `arm.py` (product body around the kernel)
[3] `tw2002_aiclient/session/protocol.py` (`propose_macro` call sites)
[4] `archive/pre-rebirth-2026-07-23/twclient/autopilot.py` (retired per-cycle EV `select()` — reference only)
[5] `tw2002_aiclient/focus_status.py` / cockpit FOCUS (strategic `ev_per_turn` display — not the live picker)
[6] Priority Engine concept + product ranker (behavior ordering, not reflex override)
[7] classify / state_parser (screen class + guard facts feeding `screen_match` / guards)
[8] auto-haggle hardening + canon/log.md 2026-07-23 (mandatory guards for on-by-default)
[9] `tw2002_aiclient/cockpit/draft_approve.py` — stub/kernel vocabularies + `bridge_to_kernel_document` (no invented defaults)
[10] canon/DECISIONS.md — Max 2026-07-29 no-invented-defaults ruling
