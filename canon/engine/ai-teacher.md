---
type: System
title: The AI Teacher — Retrospective, Human-Invoked Rule Authoring
description: The teach overlay — a human-invoked AI that reads an escalation moment after the fact and proposes a guarded rule draft for human approval, never a live keystroke.
tags: [ai-teacher, teach-overlay, rule-authoring, human-approval, on-demand, retrospective, escalation-moment, prescriptive]
timestamp: 2026-07-23T20:10:53Z
---

The AI teacher is the trainer's only use of a language model, and it is deliberately kept off the
wire. It never drives the game. When the taught app stops on a screen it does not recognize and
hands the keyboard back to the human, the human may — entirely at their own discretion — ask the AI
to look at that moment and *propose* a rule that would handle it next time. The AI reads the screen,
the parsed state, and the surrounding ledger/frames retrospectively, and returns a **draft** guarded
rule: a `when → do` a human can read, edit, approve, or throw away. Until a human approves it, that
draft is inert — it cannot fire a single keystroke. The AI is a *teacher*, an author of rules a
human ratifies; it is never one of the two live keystroke senders. This concept is prescriptive: it
specifies the author-only contract, the on-demand invocation, and the draft-and-approve gate the
reborn trainer targets, and records where the current code still carries the pre-reborn "the AI
drives" shape.

# Schema

## Author-only — the safety spine

The trainer has exactly **two live keystroke senders: `app` and `human`** (see
[trace-ledger](/engine/trace-ledger.md)). The AI is **neither.** It is a third role — *rule author* —
and its output never reaches the wire directly. Concretely:

- The AI produces **rule drafts, never keystrokes.** Its entire product is a proposed `when → do`
  plus a suggested priority and scope. That proposal is data a human reviews, not an action.
- **The AI declines the keyboard even when offered it.** If any code path were to hand the AI a
  live-driving slot, the correct behavior is to refuse and author instead. There is no mode, verb,
  or fallback in which the AI presses a key on the live connection. This is the safety spine: a
  language model's output is never trusted to move the game, only to *suggest* a deterministic
  behavior a human then approves.
- What the AI contributes is therefore measured as **rules authored and approved**, a
  teach-provenance axis — *not* a share of live keystrokes. Its live keystroke share is definitionally
  zero (see [coverage-metrics](/engine/coverage-metrics.md)).

This is the same spine every reborn concept sits on, stated from the teacher's side: the app plays
back only what it was taught and stops on the unknown; the human is the sovereign pilot and
escalation target; the AI teaches, on demand, and never acts.

## The escalation moment is the learning moment

The teacher exists to serve one recurring event. The app is playing taught behaviors deterministically;
it reaches a settled screen no armed rule recognizes; per the stop-on-unknown invariant it **STOPS,
does not guess, and hands the keyboard to the human** with a typed escalation reason (see
[control-and-escalation](/architecture/control-and-escalation.md)). That STOP is not a failure — it is
the exact moment worth learning from, because it is a concrete, real screen the trainer could not yet
handle.

At that moment the human has **three moves** (rendered as the A/R/T teach controls of the mode line —
see [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md)):

| Move | What it is | Who authors | Result |
|---|---|---|---|
| **Respond directly** | Take the keyboard (`tw attach`) and type the answer yourself. | human | A `human` keystroke; the operator steering. No rule created. |
| **Record a macro** | Teach by demonstration — capture the keystrokes that resolve this screen (`tw record`). | human (deterministic) | A macro the human can bind into a guarded rule. No AI involved. |
| **Ask AI to Analyze** | Invoke the retrospective teacher on this moment. | AI (draft) → human (approve) | A **draft** guarded rule proposed for approval. |

The first two need no AI at all. The third is this concept: the human choosing to spend an on-demand
AI pass to turn a hard screen into a proposed rule.

## Screen Analyze — the proposal

When the human invokes Analyze on an escalation, the teacher reads, retrospectively:

- the **unrecognized settled screen** (the full grid — the tier-4 frame, not just the ledger's delta
  summary — so it sees exactly what the app faced),
- the **parsed game-state** at that moment (credits, sector, turns, port posture, …), and
- the **surrounding ledger rows** for context (what led here, what it earned).

It returns a **draft rule** in the engine's own `when → do` shape (see
[rule-macro-engine](/architecture/rule-macro-engine.md)):

- **`when`** — a screen signature / guard describing *which* screen this rule answers, anchored so it
  cannot match a stale or unrelated screen (start-anchor discipline, below).
- **`do`** — the keystroke(s) or macro that resolves it.
- **suggested priority** — where this rule should sit in the ordering (see
  [priority-engine](/architecture/rule-macro-engine.md) consumers), a *suggestion* the human can override.
- **suggested scope** — `once` (a single-shot answer) or `repeating` (a loop-eligible behavior).

Every proposed `do` is a **guarded** action, not a raw keystroke blast: it must carry the
never-fire-unverified rails a live rule fires under — a **start-anchor** confirming the expected
screen is actually present before sending, and **send-and-confirm** verifying the send produced the
expected screen/state change (the −75-alignment colonist scar: a rule that fired a destructive action
against an unconfirmed screen). A draft that cannot express those guards is an incomplete draft, and
a guard is always permitted to **STOP and re-escalate** rather than fire (see
[rule-macro-engine](/architecture/rule-macro-engine.md) and
[control-and-escalation](/architecture/control-and-escalation.md)).

## The human-approval invariant

> **Every AI-authored rule is a DRAFT. An unapproved draft is inert — it can never fire a live
> keystroke. Only a human's explicit approval arms a rule; nothing the AI produces is ever
> auto-armed.**

This is absolute and admits no exception. It does not matter how confident the model is, how many
times the pattern recurred, or how routine the screen looks — the AI's proposal is a suggestion until
a human ratifies it, and an approved rule is thereafter a *deterministic* `app` behavior with no LLM
in its firing path. Approval may include the human editing the draft first (tightening the `when`
guard, changing the `do`, adjusting priority/scope). The gate is identical to the one the deterministic
candidate-miner's own drafts pass through — the two mechanisms differ only in *how* the draft was
produced, never in that it must be approved (see [candidate-mining](/engine/candidate-mining.md)).

## On-demand only — settled

**The AI proposes rules only when the human invokes Analyze.** There is no proactive, passive, or
background surfacing: the teacher does not watch the session and volunteer suggestions, does not
pre-compute proposals, and does not nudge. It runs exactly when asked, on exactly the moment the human
points it at, and is silent otherwise. This is **settled canon, not a deferred opt-in** — proactive
surfacing is explicitly out of scope (YAGNI), by operator ruling (2026-07-23). The reasons are of a
piece with the spine: an LLM that surfaced unprompted would be a step toward an LLM in the live loop,
it would spend tokens the human did not choose to spend, and it would blur the clean seam between the
deterministic app and the on-demand teacher. The deterministic candidate-miner's own retrospective
drafts (`tw analyze`) are a separate mechanism and are unaffected by this rule.

## The ethos bound on proposals

The teacher's proposals are bound by the trainer's conduct doctrine (see
[alignment-and-conduct](/doctrine/alignment-and-conduct.md)). The AI must not author a rule that:

- **initiates PvP** — combat against other players is human-gated; the app's only autonomous combat
  math is NPC-only. A rule that would open fire on a player is out of bounds.
- **exploits** a bug, dupe, or unintended mechanic, or
- **colludes** in a way the conduct doctrine forbids.

A screen that can only be resolved by such an action is one the teacher declines to author for — it
reports that it will not propose a rule, and the moment stays a human decision. The ethos bound is a
property of *what the teacher will author*, upstream of the human-approval gate, not a substitute for
it.

# Examples

```
1. The app is running a taught trade loop. It reaches a settled screen classified `unknown`
   (a mid-warp "Do you really want to warp there? (Y/N)" the armed rules didn't cover).
2. Stop-on-unknown fires: the app STOPS, hands the human the keyboard, reason = `unrecognized-screen`.
3. The human presses T ("ask AI to Analyze") on the mode line.
4. The teacher reads the full-grid frame + parsed state + recent ledger rows and returns a DRAFT:

     when:  screen_signature = warp_confirm   (start-anchored: the "(Y/N)" prompt is the CURRENT line)
     do:    send "Y"                           (send-and-confirm: expect the destination Sector body next)
     scope: once
     priority: (suggested) — resolve blocking navigation gates promptly

5. The draft is INERT. The human reads it, tightens nothing, and approves it.
6. It is now a deterministic `app` rule. Next time that exact confirm gate appears, the app answers it
   itself — no LLM, no stop — and if the post-send screen is NOT the expected destination, the
   send-and-confirm guard STOPs and re-escalates rather than blindly continuing.
```

```
Ethos-bound refusal:
- Escalation on a "Player <handle> is here. Attack? (Y/N)" screen.
- Human invokes Analyze. The teacher DECLINES to author: a Y here would initiate PvP, which is
  human-gated (alignment-and-conduct). It proposes no rule; the moment stays the human's call.
```

# Code divergence

The reborn model above is teacher-only and author-only. The current code still carries the
pre-reborn shape in several places (docs win — these are the deltas to close, recorded, not silently
conformed):

- **There is no AI-teacher module.** No code path today reads an escalation moment and returns a
  drafted guarded rule from a language model. The only "analyze" surface that exists — `analyze.py`'s
  `tw analyze <session>` — is **deterministic**: it slices the ledger by session and reuses the
  no-LLM pattern miner (`miner.py`) to rank recurring profitable input-subsequences as "candidates to
  codify." That is the *deterministic sibling* (see [candidate-mining](/engine/candidate-mining.md)),
  not this concept. The LLM Screen-Analyze that proposes a guarded `when → do` from a single
  unrecognized screen is prescriptive here and unbuilt in code. (Distinction to preserve when it is
  built: the two share the draft-and-approve gate, but the miner groups *recurring profitable*
  sequences across a session, whereas the teacher reasons about *one specific hard screen* on demand.)

- **`control_lock.py` `MODE_AI_PILOT` — RETIRED on tip (2026-08-04).** Tip keeps only
  `{app, human, spectate}`; there is no live-AI-driver mode. Historical finding + do-not-revive
  live in [control-and-escalation](/architecture/control-and-escalation.md) (and
  [alignment-and-conduct](/doctrine/alignment-and-conduct.md)). Not an open divergence here.

- **Ledger live-sender enum — tip closed.** Tip `record_do` accepts only `app`|`human`
  (`VALID_SENDERS`); there is no live `ai` default on the dispatch path. Full note under
  [trace-ledger](/engine/trace-ledger.md) / [coverage-metrics](/engine/coverage-metrics.md).

- **Pre-reborn "engine/AI keeps driving over the unknown" evidence** the teacher-only model corrects
  (owned in detail elsewhere, noted here as motivation): autopilot's *per-cycle EV action selection*
  picking a live keystroke every tick rather than stopping on an unrecognized screen (see the
  app-autopilot-model / priority-engine findings), and the **verified 78-turn auto-haggle misfire** —
  a deterministic resolver that kept firing on a money path without a fresh-render/send-and-confirm
  gate (see [auto-haggle](/engine/auto-haggle.md), a real money-path defect). Both are the shape the
  reborn spine forbids: an automatic driver acting on a screen it had not confirmed. They are not
  AI-teacher code, but they are why the teacher is author-only and why every proposed `do` must carry
  start-anchor + send-and-confirm guards.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot and escalation target; the app
  plays back only taught screens and STOPS on the unknown; the AI is a retrospective, human-invoked
  rule author and never a live keystroke; every rule — human- or AI-authored — is human-approved
  before it can fire; never fire an unverified/destructive action (start-anchor + send-and-confirm);
  a guard may STOP and escalate instead of firing; combat/PvP is human-gated, NPC-only math.
- Operator ruling (2026-07-23): AI rule-surfacing is **on-demand only and settled** — proactive/passive
  surfacing is explicitly out of canon; ai-teacher and candidate-mining are kept split along the
  LLM-vs-deterministic seam.
- Project canon: [trace-ledger](/engine/trace-ledger.md) (the `{app, human}` live-sender invariant and
  the AI-as-author provenance axis), [control-and-escalation](/architecture/control-and-escalation.md)
  (stop-on-unknown and the escalation reason-code catalog),
  [rule-macro-engine](/architecture/rule-macro-engine.md) (the `when → do` guarded-rule shape and its
  rails), [candidate-mining](/engine/candidate-mining.md) (the deterministic sibling that shares the
  approval gate), [coverage-metrics](/engine/coverage-metrics.md) (AI as a teach-provenance axis, live
  share ≡ 0), [mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md) (the A/R/T
  teach moves at the escalation moment), [auto-haggle](/engine/auto-haggle.md) (the 78-turn misfire
  finding), [alignment-and-conduct](/doctrine/alignment-and-conduct.md) (the ethos bound on proposals).
- Reimagined from `knowledge/architecture/autonomy-loop.md` (the session-retro half), re-rooted in the
  reborn teacher-only vision — the old "session retro mines what the AI did to codify it" framing is
  recast here as an on-demand, author-only, human-approved proposal, and its autonomy-ratio pairing is
  deliberately *not* carried (that is recast under [coverage-metrics](/engine/coverage-metrics.md)).
- Code modules (plain text): `analyze.py` (the deterministic session-retro that is the sibling, not
  this concept), `miner.py` (the pattern miner it reuses), `ledger.py` (the read substrate + `actor`
  default divergence), `control_lock.py` (`MODE_AI_PILOT` divergence), `classify.py` (screen
  classification whose `unknown` result is the escalation trigger), `watch.py` (the settle-edge stream
  the escalation surfaces on). Internal design history: the TW-12 session-retro and the §22/§23
  autonomous-trainer + game-introspection epics, reimagined here under the reborn constraints.
