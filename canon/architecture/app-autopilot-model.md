---
type: System
title: The APP Autopilot Model — the Taught-Behavior Run-Loop
description: The runtime that runs a multi-screen taught behavior over many cycles — it plays the next taught step, re-reads the screen, re-validates the match every cycle, stops the instant a screen is unrecognized, and only ever runs after a human arms it.
tags: [architecture, autopilot, run-loop, stop-on-unknown, arm-confirm, human-in-the-loop]
timestamp: 2026-07-23T20:21:17Z
---

The [Rule–Macro Engine](/architecture/rule-macro-engine.md) decides ONE cycle:
`when(screen_match + guards) → do(macro)`. This concept is the **runtime that loops that
decision** across the many cycles a real behavior takes — a trade chain, a background pair-trade,
an explore sweep. The engine answers "what do I play on the screen in front of me right now"; the
run-loop is the thing that plays it, re-reads the resulting screen, and decides whether it may go
on. The reborn contract — **re-validate every cycle, STOP on the unknown, run only after a human
arms it, and STOP (never rotate) on depletion** — is a property of *this loop*, asserted here, not
an emergent side effect of the single-cycle decision. The invariants themselves are owned by
[Control & Escalation](/architecture/control-and-escalation.md); this concept specifies how the
loop enforces them across a multi-cycle run and homes the modules that run it.

# The Run-Loop Model — Play-the-Taught-Step, Then Re-Read

The reborn cycle is a mechanical four-beat loop, and every beat is a lookup or a playback — **zero
AI reasoning runs per cycle**:

1. **ASSESS** — classify the current settled screen (see
   [Screen Understanding](/engine/screen-understanding.md)) and read its best-effort state. This
   is recognition, not inference: the screen is either one the active taught behavior expects, or
   it is not.
2. **MATCH** — check the settled screen against the active behavior's expected next screen
   (`screen_match` + guards). A match means "the behavior's next taught step legitimately applies
   here." A non-match is not a puzzle to solve — it is an escalation trigger (see below).
3. **PLAY** — replay the next taught step of the behavior (the macro's keystrokes), then wait for
   the screen to settle again.
4. **RE-READ** — return to ASSESS on the *new* settled screen and repeat.

This is deliberately **play-the-taught-macro-then-re-read**, not per-tick expected-value
goal-seeking. The loop never re-derives, from scratch, "what is the single highest-EV action to
send right now" — that framing is the retired AI-first model. Which taught behavior is *running*
is a decision made once, up front, when the human arms it; the strategic
[Priority Engine](/engine/priority-engine.md) may **rank and order** which taught behaviors are
offered or which runs next, but it never gets to pick a live keystroke that would override an
unrecognized screen. The run-loop plays what it was taught, in the order the behavior prescribes,
and re-checks reality at every step.

# Re-Validate Every Cycle — Stop-on-Unknown at Every Tick

The single most important property of this loop: **`screen_match` is re-checked on every cycle,
not just at entry.** A behavior that was armed on a recognized screen can, three steps in, land on
a screen the app has never been taught — a surprise interstitial, an unexpected combat prompt, a
plague notice, a menu variant. The instant the freshly-settled screen fails to match the active
behavior's expected next screen, the loop **halts and hands the keyboard to the human**. It does
not retry, does not guess a recovery keystroke, does not fall back to a lower-confidence action.
This is the runtime expression of [Control & Escalation](/architecture/control-and-escalation.md)'s
escalate-on-unknown handoff — the loop is simply the place where "every cycle" becomes literal.

Mid-run STOP and entry-time STOP are the same mechanism, deliberately: there is no "we're already
committed, push through" state that would let an in-flight behavior keep sending into a screen it
no longer recognizes. Recognition is re-earned every tick, or the loop stops. (The STOP banner,
reason-code catalog, and the three human teach-moves that follow are owned by
[Control & Escalation](/architecture/control-and-escalation.md) and the
[Mode Line & Teach Controls](/surfaces/mode-line-and-teach-controls.md) — this concept only
guarantees the loop *reaches* that handoff on the first unrecognized frame.)

# Arm-Confirm — No Run Without a Human's Go

A taught behavior or a background repeating loop is **human-armed before it can run.** There is
never one keystroke from idle to a live multi-cycle run that spends real credits or turns. Arming
is an explicit, confirm-gated act: the human selects a behavior, sees what it will do, and
confirms; only then does the loop begin. This closes the class of scars the reborn vision exists
to prevent — an unattended macro auto-firing a destructive or money-path prompt (the −75-alignment
colonist scar and the 78-turn auto-haggle misfire; see
[Auto-Haggle](/engine/auto-haggle.md) and
[Action Safety Guards](/doctrine/action-safety-guards.md)). The arm gate is a **required, external
input** to the loop, not an internal self-check the loop could grant itself: the runtime is armed
by the human's confirmed decision and re-reads that arm state at its own send choke-point, so
disarming (stopping) reaches an in-flight run within one step, not only at the next cycle boundary.

# Guard-STOP-Not-Rotate

When a running behavior's guards detect **depletion or hazard** — a trade source exhausted, a
route blocked by mines or fighters, a balance fallen through the floor — the loop **STOPS and
escalates.** It does **not** autonomously rotate to a new source, pick a different chain, or
re-plan around the obstacle. Depletion is an escalation moment, surfaced to the human (who may
re-target, teach a rotation, or re-arm), never a trigger for the app to keep driving on its own
initiative. This is the runtime owner of the "depletion → STOP-guard" contract that
[Trade Loops & Chains](/strategy/trade-loops.md) prescribes for its pair-trade and chain behaviors:
the strategy layer says *depletion means stop*; this loop is what actually stops. The reborn model
explicitly retires the AI-first "never idle, keep driving, rotate to the next-best source"
appetite — an idle app waiting on the human is correct behavior, not a gap to be filled.

# Chain Execution — A Sequence of Taught, Re-Validated Steps

A trade chain (`navigate → dock → buy → navigate → dock → sell → repeat`) is the canonical
multi-cycle behavior this loop runs. It is executed as a **sequence of taught steps, each one
re-validated against the live screen before it is played** — never a blind pump of a
pre-computed keystroke sequence:

- Every send is preceded by a **fresh render** and a re-classification of the current screen; the
  next keystroke is played only if that live screen is exactly the shape that step expects (the
  command prompt before a warp, the port menu before a dock-select, the quantity prompt before a
  quantity). Any other shape is an unrecognized-mid-run STOP.
- The behavior may send only its taught, safe keystrokes — enter-a-port, trade-not-attack, a bare
  sector number, a bounded quantity, or accept-the-standing-offer. Combat, Genesis, colonist-load,
  and PvP-initiate keystrokes are structurally unreachable from the chain runner (the Paladin
  boundary; see [Alignment & Conduct](/doctrine/alignment-and-conduct.md)).
- The turn budget and credit floor are re-checked at each hop and each dock boundary — a hop that
  would strand the pilot below the turn reserve STOPS before it docks; a below-floor balance STOPS
  before it buys; cargo already paid for is never silently stranded to report a round-trip that
  never happened.
- A per-step **abort predicate** and **arm predicate** are checked at the same choke-point as every
  other guard, so a human's STOP (or a disarm) halts an in-flight chain within one send-step.

The chain runner is a taught, human-armed behavior with stop-on-unknown re-validation at every
step — not an autonomous "drive an arbitrary freshly-discovered profit cycle end-to-end on the
app's own initiative" primitive.

# Background AUTO-LOOP Posture

A repeating behavior (a `scope: repeating` macro — see [Macros](/engine/macros.md)) runs on the
daemon's background AUTO-LOOP driver under the `auto_loop` control mode (see
[Control & Escalation](/architecture/control-and-escalation.md) for the mode's exclusivity rules).
The reborn posture is a strict specialization of everything above:

- **Human-armed** — the loop enters `auto_loop` only via its own explicit start, which the human
  confirms; it can never read as "on" without an actually-running driver thread behind it.
- **Stop-on-unknown mid-loop** — a cycle that lands on a screen the recorded skill no longer
  matches halts the whole loop exactly like any single-cycle surprise (`halt-on-divergence`), and
  the keyboard returns to the human.
- **Depletion → STOP** — the loop's pre-cycle floor check STOPS the loop (escalating) on a
  below-floor or unconfirmable balance; it never rotates to a new skill or source.
- **Not an always-on autonomous trader** — the loop is bounded (a hard cycle cap applies
  regardless of caller intent [hypothesis — the cap is a configurable safety default, not a game
  fact]), pause/stop-able from the cockpit, and stops itself the moment the human takes the
  keyboard.

# The §22 Capstone, Recast (TW-23)

The original AI-first §22 capstone — an unattended AI goal-seeker that keeps driving toward a
target (e.g. "double the starting credits") on its own initiative — is **re-scoped, not built as
specced.** In the reborn model the capstone becomes: **the APP orchestrates ONLY taught behaviors
and STOPS on the unknown, and every run is execution-gated behind a human arm.** This
taught-behavior-orchestration concern lives here, in the control-runtime layer, deliberately moved
out of the [Priority Engine](/engine/priority-engine.md): ranking *what to pursue* is a strategic
concern, but *running a behavior until an unknown screen stops it* is a control-runtime concern,
and filing it under the strategic ranker was the mis-placement this recast corrects. The priority
layer feeds ordering into this loop; this loop owns the STOP.

# Code Divergences (DOCS WIN)

- **`autopilot.py` — tip closed (archive / do-not-revive).** Pre-rebirth
  `archive/.../autopilot.py` was a per-cycle EV action-picker
  (`AutopilotEngine` ASSESS→SELECT→EXECUTE→RECORD). Tip has **no**
  `tw2002_aiclient/autopilot.py` and no `tw autopilot` verb. Live taught
  playback is `loops/player.py` + `session/autoloop.py` (novelty-halt,
  human-armed). Do not revive the archive EV driver under a new name.
- **`EXPLORE_BASELINE_EV = 0.01` — tip subdivergence closed (display-only).** Archived
  `autopilot.py` seeded this constant as a "no idle" auto-driver so a tick always manufactured an
  explore action. The surviving constant lives in
  `tw2002_aiclient/focus_status.py` as a **suggestion-only** FOCUS floor (comment: keep explore
  visible when the map still has work — never sends / arms / drives a keystroke). The never-idle
  *driver* appetite is abolished on tip. Whether a display-only floor is itself correct policy vs a
  strict novelty-halt empty FOCUS remains a separate gated design question
  (`WO-FIX-EXPLORE-BASELINE-EV-NEVER-IDLE` / exploration-policy). Recorded here as closed for the
  "auto-driver" half only.
- **`priority_engine.recommend_actions()` as live `select()` override — tip closed with
  `autopilot.py`.** Archive wiring let the priority engine re-pick the live keystroke each tick.
  Tip `priority_engine.py` is strategic ranking / FOCUS only — it does **not** override a taught
  replay send. (Strategic half still recorded in [Priority Engine](/engine/priority-engine.md).)
- **`trade_driver.py` guarded-chain divergence resolved by ADR-003.**
  `TradeChainRunner` is now the only product owner of `run_chain()`: it
  requires an exact human-confirmed fingerprint, re-runs discovery before the
  lock, executes one pass, and surfaces each `ChainHold` as a terminal STOP.
  Fresh-render, arm/abort, floor, reconciliation, and Paladin checks remain at
  every send. No finder-initiated launch or replacement-chain rotation exists.
- **`session/autoloop.py` is the background AUTO-LOOP driver** (ported from archive
  `twclient/loop_player.py`). It runs a saved skill as a bounded (hard cycle cap), human-armed,
  pause/stop-able background thread that halts on replay divergence (`surprise`) and on a
  fail-closed below-floor / unconfirmable-balance check (`floor_reached` / `credits_unknown`),
  entering/leaving `auto_loop` exclusively. It is the closest of the three to the reborn posture
  already; its only divergence is the surrounding "unattended autonomous trader" framing, which
  this concept recasts to "human-armed repeating taught behavior that STOPs on the unknown and on
  depletion." Recorded as a divergence in framing.
- **§22 / TW-23 capstone re-scoped.** The unattended AI-goal-seeking "double the starting credits"
  capstone is re-scoped to "APP orchestrates ONLY taught behaviors and STOPS on the unknown,
  execution-gated," and its home is moved here from the priority engine (see the recast section
  above). Recorded as a scope divergence from the original spec.

These are documentation-only findings — this concept edits no code. The archived per-cycle EV
picker / live priority override remain do-not-revive; tip's `EXPLORE_BASELINE_EV` is suggestion-only
in FOCUS. Reframing remaining drivers as human-armed taught behaviors, and the design ruling on
whether a display-only explore floor should retire, are separate work orders.

# Citations

[1] archive `twclient/autopilot.py` (historical ASSESS→SELECT→EXECUTE→RECORD / per-tick EV /
`EXPLORE_BASELINE_EV` "no idle" — do-not-revive); tip `tw2002_aiclient/focus_status.py`
(`EXPLORE_BASELINE_EV` suggestion-only FOCUS floor)
[2] `tw2002_aiclient/trade_driver.py` (`run_chain()` end-to-end chain runner; fresh-render gate per send; required `is_armed`/`should_abort` predicates; `ChainHold` depletion/turn-floor/cargo-stranded STOPs; Paladin `_ALLOWED_LETTER_SENDS` allowlist)
[3] `tw2002_aiclient/session/autoloop.py` (background AUTO-LOOP driver; ported from archive `twclient/loop_player.py`; human-armed enter; bounded cycle cap; pause/stop; `surprise`/`floor_reached`/`credits_unknown` STOPs)
[4] `tw2002_aiclient/session/control_lock.py` (active-driver slot; App/Human live-driver dual; AUTO-LOOP enter/leave fencing)
[5] `tw2002_aiclient/priority_engine.py` (`recommend_actions()` strategic ranker — informs behavior ordering, not a live per-cycle picker; `MIN_CHAIN_LINKS_TO_EXECUTE` execute floor)
[6] `tw2002_aiclient/session/settle.py` (`send_and_confirm` — the send-and-confirm net every driver send routes through)
[7] canon/architecture/control-and-escalation.md (owns the stop-on-unknown, arm-confirm, and escalation-handoff invariants this loop enforces)
[8] canon/architecture/rule-macro-engine.md (the single-cycle `when→do` decision this run-loop repeats)
