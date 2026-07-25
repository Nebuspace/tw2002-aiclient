---
type: System
title: Control & Escalation
description: The App/Human control dual, the non-driving AI teach overlay, and the escalate-on-unknown handoff that hands the keyboard to the human the instant autopilot meets a screen it cannot match.
tags: [architecture, control, escalation, human-in-the-loop]
timestamp: 2026-07-23T18:55:04Z
---

Live control of the one game connection is a **dual**, not a triad: **App** (deterministic
autopilot) and **Human** (sovereign pilot) are the only two actors that ever hold the keyboard.
**Spectate** is read-only observation chrome — **not a Mode** and not a third dual seat (ADR-002).
The **AI** sits outside this rotation entirely — it is a retrospective, human-invoked teach overlay,
never a live driver. This concept specifies the control-flow mechanics behind
[the North Star](/architecture/north-star.md)'s three actors; it does not specify rule/macro
internals (see [the Rule–Macro Engine](/architecture/rule-macro-engine.md)) or the keystroke-ledger
substrate (see [the Session Engine](/architecture/session-engine.md)).

# The Control Dual

- **App** drives by matching the current screen against its guarded, prioritized rule set and
  playing back a macro on a match. Zero AI reasoning runs per cycle — recognition and playback are
  mechanical lookups, not inference. Default when the client runs = App/autopilot.
- **Human** is the sovereign pilot. The human holds the keyboard whenever the app cannot recognize
  the screen in front of it, and also by an explicit Mode switch at any time, for any reason. The
  human's claim on the keyboard is never conditional on the app's failure — it is unconditional.
- **Spectate** drives nothing. It is read-only observation chrome a client can use without ever
  entering the App/Human Mode dual.
- **AI teach overlay** is not a control mode and never appears in the mode line as a thing that
  "drives." It is invoked by the human, after the fact, to review what just happened and propose a
  rule. It never emits a live keystroke, and it is never offered the keyboard.

# The Mode Switch

Mode is **Ctrl-A** in the trainer UI (ADR-002 — see [Mode Line](/surfaces/mode-line-and-teach-controls.md)).
It toggles live control between **App** and **Human**. There is no third position on that toggle for
"AI drives" — the AI has no seat in the mode switch at all. No single printable may be Mode; while
Human is attached, bare `M` is TW Move (passthrough), not Mode. Switching to Human is always
immediate and always succeeds; the app never gets to refuse or negotiate for the keyboard.

# Escalate-on-Unknown

This is the defining mechanic of the control model. When the App autopilot encounters a screen
with no matching rule, it does not guess, retry, or reach for a default action — it **stops** and
hands the keyboard to the Human, raising a clear escalation signal. This is an App→Human
transition, not an App→AI transition; the AI is never consulted in the moment.

At the escalation moment, the Human has three moves (mirroring
[the North Star](/architecture/north-star.md)'s escalation-moment framing, specified here at the
control-flow level rather than the rule-schema level):

1. **Respond directly** — play the screen by hand and let control continue from there. Nothing is
   taught; the app will escalate again on the identical screen next time.
2. **Record a macro** — capture the human's keystroke response as a new guarded rule, the
   reflex-layer write path. The next time the app meets a matching screen, it plays the macro
   itself and never escalates for it again (barring a guard failure).
3. **Ask the AI to Analyze** — after the fact, invoke the AI teach overlay to review the
   escalation and propose a rule or macro. The AI's proposal is a draft, not a live action — it
   still has to clear the approval gate below before it can ever fire.

# Two Invariants

**(a) Human approval gate.** Every rule that can fire — whether the human recorded it directly or
the AI authored it via Analyze — is approved by the human before it is live. Nothing the AI writes
drives a keystroke autonomously; authorship and approval are always separate steps, and the human
holds the second one exclusively.

**(b) AI is on-demand only.** The AI teach overlay acts only when the human invokes it, at or after
an escalation. It is not a background process that watches continuously and drives, nor one that
auto-applies its own proposals. Whether the AI may *proactively surface* candidate rules from
passive observation (without being asked) is an **open, deferred question** — the default
behavior specified here is on-demand-only, and nothing in this concept authorizes a proactive
variant.

# Keystroke Attribution

Live keystroke senders are **`{app, human}`** only. "AI" is a rule *author*, never a live *sender*
— an AI-authored rule that a human has approved is subsequently played back by the App the same as
any human-recorded rule; the keystroke that fires is attributed to the App executing an approved
rule, not to the AI. This refines the informal three-actor framing at the mode-switch/ledger level.
The attribution substrate that records who sent what lives in
[the Session Engine](/architecture/session-engine.md) — this concept does not specify its schema.

# Escalation reason-code catalog

Every App→Human STOP carries a **typed reason code**, not a free-text string. When autopilot stops
and hands the keyboard back, it names *why* with a code drawn from a fixed catalog; the human-facing
STOP banner renders the code's short label, and the same code is what the ledger and any spectator
read. Reason is a typed value throughout — the display label is a lookup, never the wire form.

The catalog as it actually exists is the `INTERVENTION_REASON_LABELS` map in
`twclient/intervention_labels.py` — the single source of truth shared by the trainer/product
adapters and the read-only spectate layout. Its codes, grouped by the STOP-cause family they
express:

| reason code | human label | STOP-cause family |
|---|---|---|
| `autopilot_halted` | autopilot halted | **guard-STOP** — a guarded rule refused to fire (guard tripped), so autopilot stopped rather than play an unsafe macro |
| `autopilot_no_candidates` | autopilot no candidates | **unrecognized-screen** — no rule matched the current screen; nothing to play, so hand off |
| `explore_exhausted` | explore exhausted | **novelty-halt** — the exploration budget ran out with no recognized continuation |
| `autopilot_max_ticks_exhausted` | autopilot max ticks exhausted | **depletion** — the per-run tick budget is spent; stop and let the human decide whether to continue |
| `autopilot_game_select` | autopilot game select | **hazard** — autopilot reached a game-select / session-boundary screen it must not auto-answer; the human owns that choice |
| `human_attach_blocks_trainer` | human attach blocks trainer | **human-sovereignty preemption** — a human attached interactively, so the trainer yields the keyboard unconditionally |
| `credits_unknown` | credits unknown | **desync** — the credits field of the world-model could not be read; autopilot will not act on an unknown balance |
| `credits_stale` | credits stale | **desync** — the last-known credits value is too old to trust for a decision |
| `fighters_unknown` | fighters unknown | **desync** — the fighters field of the world-model could not be read |
| `fighters_stale` | fighters stale | **desync** — the last-known fighters value is too old to trust for a decision |

The catalog is **open by construction**: `intervention_reason_label()` passes an unrecognized code
through as its own text (and maps an empty/`None` code to `"?"`), so a new STOP cause can ship a new
code before a label exists without breaking any surface — it simply renders as the raw code until a
label is added.

The **mode-line-and-teach-controls** surface renders the STOP banner from this typed catalog: it
takes the escalation's reason *code*, resolves it through `intervention_reason_label()`, and shows
the resulting short label — the banner reason is a typed code, not free text.

**Code divergence.** The STOP-cause families above (guard-STOP, unrecognized-screen, novelty-halt,
depletion, hazard, desync, human-sovereignty preemption) are the canonical taxonomy; the actual
`INTERVENTION_REASON_LABELS` map does not yet carry a *dedicated* code for every family boundary —
e.g. "unrecognized-screen" and "novelty-halt" are both expressed through the autopilot/explore
codes above rather than a single generic `unrecognized_screen` code, and there is no distinct
`guard_stop` code separate from the general `autopilot_halted`. The map as-is is the ground truth
this catalog is grounded in; tightening the codes to one-per-family is a possible future code change,
recorded here as divergence — the doc is not conformed down to the current code.

# Schema

| mode | who drives | how entered | emits live keystrokes? |
|---|---|---|---|
| App (autopilot) | App | default control state; Ctrl-A Mode from Human; a running background loop | Yes — macro playback only, on a recognized screen |
| Human | Human | escalation handoff on an unrecognized screen; explicit Ctrl-A Mode; attaching interactively at any time | Yes — the human's own input |
| Spectate | nobody | observation chrome (not a Mode dual seat) | No |
| AI teach overlay | nobody (not a control mode) | human invokes "Analyze" at/after an escalation | No — proposes a rule for human approval; never sends |

# Examples

An escalation handoff, end to end:

```
1. App is driving. It recognizes each screen in sequence and plays the matching macro.
2. App meets a screen with no matching rule. It stops immediately and hands the keyboard
   to the Human — no guess, no retry, no default action.
3. Human takes the keyboard, answers the prompt directly, and hits Record on the way out,
   capturing the keystroke as a new guarded rule (scope: repeating).
4. Control returns to App. The next time the identical screen appears, App recognizes it,
   plays the recorded macro, and never escalates for it again.
```

A mode-switch example, independent of any escalation:

```
1. App is driving, mid-session, nothing unrecognized has happened.
2. The Human hits Ctrl-A (Mode) because he wants to fly a stretch of the game by hand.
   The switch succeeds immediately — App never gets to finish "one more macro" first.
3. Human plays several turns directly. Bare `M` reaches the game as Move. No rule is written
   unless the Human explicitly chooses to Record one of those turns.
4. The Human hits Ctrl-A again to hand control back to App, which resumes autopiloting from
   whatever screen is now on screen.
```

# Code Divergence

`control_lock.py` (the daemon's existing control-mode state machine) currently defines
`MODE_AI_PILOT` as a live-drive mode: the default mode, in which "the AI drives," with
`do`/`send`/`play`/`replay`/`haggle` verbs dispatching keystrokes while it holds. Under this
canon, an AI live-drive mode does not exist — the AI never sends a live keystroke, by either of
the two invariants above. `MODE_AI_PILOT` as a *drive* mode is a direct contradiction of ruled
canon and is slated for retirement or repurposing: most plausibly as the invocation point for the
AI teach overlay (an "Analyze" trigger) rather than as a mode that grants send-verb access. This is
a documentation-only finding — `control_lock.py` is not edited by this concept; the code fix is a
separate future work order.

The other three existing modes map cleanly onto this canon:

| `control_lock.py` mode | canon mode |
|---|---|
| `human` (`MODE_HUMAN`) | Human |
| `auto_loop` (`MODE_AUTO_LOOP`) | App (autopilot) — the background LoopPlayer driving a learned skill solo |
| `spectate` (`MODE_SPECTATE`) | Spectate |
| `ai_pilot` (`MODE_AI_PILOT`) | **no canon equivalent as a drive mode** — see above |

# Citations

[1] USERDOCS/aiclient_ui.md (mode line + hotkeys sketch)
[2] canon/log.md 2026-07-23 (AI role ruling)
[3] twclient/control_lock.py (existing control-mode state machine)
[4] twclient/intervention_labels.py (enumerated intervention reason-code → human-label map; shared by product adapters and spectate layout)
