---
type: Vision
title: North Star — The Human-Piloted Trainer
description: tw2002-aiclient is a human-piloted trainer whose app autopilots the screens it has been taught, escalates every unknown to the human, and lets an observing AI codify the human's responses into its growing repertoire.
tags: [vision, north-star, human-in-the-loop, escalation, trainer]
timestamp: 2026-07-23T18:03:04Z
status: SIGNED
---

> **SIGNED** Max 2026-07-25 (Batch 2/3) — this file (+ settled AI on-demand-only in teacher concepts)
> is accepted vision. Align freely; do **not** invent new one-cockpit prose beyond this text without
> a new Max ask.

tw2002-aiclient is a **human-piloted trainer** for TradeWars 2002 — not an AI that plays the
game. The human flies; the app carries the load it has already been taught how to carry; the AI
teaches. This document supersedes the earlier AI-first vision (an AI pilot that graduates toward
flying itself as an "autonomy ratio" crosses 50%) — that framing sidelined the human as the
metric climbed, and it is retired, not extended.

# The Three Actors

- **Human — sovereign pilot and escalation target.** The human plays the game. Every screen the
  app has not been taught how to handle lands, unconditionally, in front of the human. The human
  is never a fallback and never sidelined by a rising automation number — the human is who the
  whole system exists to serve.
- **App — the deterministic autopilot.** The app plays back only the screens it has been taught:
  a recognized screen matched against a guarded rule that fires a macro (a keystroke sequence).
  Zero AI reasoning runs per cycle — recognition and playback are mechanical. The instant the app
  meets a screen it does not recognize, it stops and hands the keyboard back to the human. It
  never guesses.
- **AI — the teacher, never a pilot.** The AI watches the session and helps grow the app's
  repertoire, but it never drives — not on its own initiative, and not even when offered the
  keyboard. Its help is invoked by the human and retrospective: it analyzes what just happened and
  proposes a rule for the human to approve, never reasoning live over the next keystroke.

# The Escalation Moment Is the Learning Moment

Escalation is not a failure mode to be minimized into oblivion — it is the mechanism by which the
app gets better. When the autopilot escalates on an unrecognized screen, the human has three
moves:

1. **Respond directly** — just play the screen, the way any human would, and move on.
2. **Record** a macro — teach the app how to handle this exact prompt or screen the next time it
   appears, capturing the keystroke sequence as a reusable response.
3. **Ask the AI to analyze after the fact** — the AI reviews what just happened and authors its
   own macro or rule for that situation, offloading the judgment call from the human to the AI's
   retrospective analysis.

Every one of these three moves is a deposit into the same growing repertoire. The app does not
get smarter by an AI reasoning harder in the moment; it gets smarter because a human — directly,
or via an AI acting on the human's invitation — taught it one more thing.

# Two Layers of App Behavior

The app's deterministic behavior lives on two layers. Both are introduced here at vision
altitude only; their internals belong to their own concepts.

- **The reflex layer** — a rule–macro engine: guarded, prioritized rules of the shape
  `when(screen_match + guards) → do(macro)`, each with a `scope` of `one-shot` or `repeating`.
  This is the mechanism the Record and Analyze flows above write into. See
  [the Rule–Macro Engine](/architecture/rule-macro-engine.md).
- **The strategic layer** — a priority engine that decides *what to pursue* at the level above
  any single screen: identifying turns and credits, finding StarDock, building a trade loop,
  buying fighters and cargo holds. This layer sets direction; the reflex layer executes the
  keystrokes that direction implies. See [the Priority Engine](/engine/priority-engine.md).

The control model (who holds the keyboard, and exactly how the handoff between app and human
happens) and the substrate both layers run on are their own concepts — see
[Control & Escalation](/architecture/control-and-escalation.md) and
[the Session Engine](/architecture/session-engine.md).

# The Win Condition

The win condition is **not** "the machine flies itself." That framing — an autonomy ratio
crossing a majority share, at which point the AI is said to be piloting — is explicitly retired.
The reborn win condition is a **trustworthy human co-pilot**: a system that shoulders more of the
*known* over time while always, unconditionally, deferring the *unknown* back to the human. If
progress is measured at all, it is framed as **the share of the known that the autopilot now
handles** — never as a contest the app is trying to win against the human, and never as a
threshold past which the human stops being needed.

# Alignment Ethos

The autopilot's behavior stays protective-by-default: it never initiates unprovoked PvP. Any
player-facing combat — even in defense of another player — is the human operator's in-the-moment
call, never an autonomous trigger. This ethos is unchanged from the prior vision and carries
forward unmodified; it is not up for renegotiation by anything written above.

# Examples

An illustrative escalate-then-teach arc:

```
Turn 1:  Autopilot hits an unrecognized "Deploy Fighters? (Y/N)" prompt on a sector it has
         never seen before. It stops. The human answers "N" directly (move 1) and play
         continues — nothing is taught yet.

Turn 40: The same prompt appears again, on a different sector. The human this time hits
         Record, answers "N", and stops recording — the app now has a guarded rule:
         when(screen_match="Deploy Fighters?") -> do(macro="N"), scope: repeating.

Turn 41+: The prompt reappears. The app recognizes it, plays the macro, zero reasoning,
         zero escalation. The human is not asked again unless a guard on the rule fails —
         at which point it escalates once more, and the loop repeats.
```

# Citations

[1] USERDOCS/priority_engine.md (strategic-layer draft)
[2] USERDOCS/aiclient_ui.md (trainer-UI sketch)
[3] canon/log.md 2026-07-23 (founding decision — the three ruled forks)
