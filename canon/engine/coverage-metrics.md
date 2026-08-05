---
type: System
title: Coverage & Autonomy Metrics — How Much of the Known the App Handles
description: The recast headline gauge — the taught app's live-keystroke coverage measured against how often it escalates to the human — built on trace-ledger actor attribution, with token efficiency as the same axis and AI teaching contribution as a separate provenance measure.
tags: [coverage, autonomy-ratio, metric, escalation, token-efficiency, provenance, prescriptive]
timestamp: 2026-07-23T20:20:47Z
---

Coverage is the trainer's headline number: **of the live keystrokes crossing the one game
connection, what share did the taught app handle on its own, and how often did it have to hand the
keyboard back to the human?** It is the reborn recast of the old "autonomy ratio," and the recast is
not cosmetic — the metric's *meaning* changed with the vision. The old ratio scored an AI-pilot
against a deterministic trainer and treated a rising number as the app graduating toward flying
itself. The reborn trainer has no live AI pilot and no graduation: the human is the sovereign pilot,
the app plays back only what it was taught and stops on the first screen it does not recognize, and
the AI is a retrospective teacher that never presses a key. So the gauge is re-pointed at the only
question that still matters — *how much of the known does the taught app carry, and how often does it
escalate* — and every escalation is a healthy, expected event, not a failure the number should shame
into zero. This concept is prescriptive: it specifies the recast metric, its denominator, the
token-efficiency identity, and the separate teaching-provenance axis, and it reads its counts from
the [trace ledger](/engine/trace-ledger.md) — it computes nothing on its own that would drive a live
keystroke.

# Schema

## The coverage ratio

Coverage is computed over a rolling window of ledger rows, counting each row by its `actor`. The
trainer has exactly two live keystroke senders — `app` and `human` (the attribution invariant lives
in the [trace ledger](/engine/trace-ledger.md)) — so the ratio is simply:

```
coverage = app / (app + human)
```

over the window, where `app` is the count of deterministic no-LLM sends (a taught macro replaying, a
guarded rule firing, a repeating loop stepping) and `human` is the count of keystrokes the operator
typed directly. Its complement, `human / (app + human)`, is the **escalation frequency** — how often
the human had to drive.

This denominator is the load-bearing change from the old formula. The pre-reborn ratio was
`trainer / (ai + trainer)` and **excluded** `human` entirely, on the reasoning that a human driving
was "the operator steering, not a contest between AI and trainer." The recast **includes** `human` in
the denominator on purpose, because under the reborn vision a human keystroke *is* the very thing the
metric exists to measure: the app met a screen it could not handle, stopped, and escalated. Coverage
and escalation are two readings of one quantity — the share of live keystrokes the app carried versus
the share it handed back.

| Term | Meaning |
|---|---|
| `app` | Live keystrokes the taught app played deterministically (macro replay, guarded rule, loop step). Zero AI reasoning at send time. |
| `human` | Live keystrokes the operator typed directly — every one an escalation or a deliberate takeover. |
| `coverage` | `app / (app + human)` over the window — the app's share of live driving. |
| `escalation frequency` | `human / (app + human)` — coverage's complement. |

## `ai` is not a live share

There is **no live `ai` sender**, so `ai` never appears in this denominator, and the app's live AI
share is **definitionally 0** (J1). This is forced by the teacher-only ruling: the AI reads a screen
or a session retrospectively, on human demand, and proposes a guarded rule draft for the human to
approve; an approved rule becomes a deterministic behavior the *app* later plays. Any AI influence on
live play has already been laundered through human approval into an `app`-attributed macro by the time
a key is pressed. Reporting an "AI live share" would be reporting a quantity that is always zero and
would falsely imply a live AI pilot the reborn trainer does not have.

## AI teaching contribution — a separate axis

The AI's contribution is real, but it is a property of *rule authorship*, not of any live keystroke —
so it is measured on its own axis, never folded into the coverage ratio:

**AI teaching contribution = the count (or share) of guarded rules the AI drafted that the human
approved and that are now app-playable.** It answers "how much of the app's grown repertoire did the
AI teacher help author," which is a provenance question about the *rules*, not a driving question
about the *keystrokes*. A rule the AI drafted and a rule the human recorded by hand both fire as
`app` at send time and both count identically toward coverage; they differ only on this authorship
axis. Keeping the two axes separate is what lets the trainer credit the teacher without ever
pretending the teacher drove.

## The coverage meter's three figures

The cockpit's auto-% meter (the UI face lives in [trainer-cockpit](/surfaces/trainer-cockpit.md))
shows the **App-vs-Human live share** — two live figures, not three (operator ruling, 2026-07-23):

- **App %** — `coverage` as above.
- **Human %** — `escalation frequency`.
- **AI** — shown, if at all, as the *teaching-provenance* figure (rules authored/approved), explicitly
  labelled as a separate axis, never as a third slice of the live pie. Its live share is 0.

The earlier draft's "APP vs AI vs Human" three-way live meter is retired: a live AI slice would always
read 0 and would reintroduce exactly the AI-pilot framing the reborn vision removed.

# The token-efficiency identity

Coverage and token efficiency are **the same axis measured in two units** (J2). Every keystroke the
deterministic app plays is a keystroke that did *not* require a live LLM turn to decide — so each
`app` send is simultaneously:

- a **coverage gain** — one more live keystroke the taught app carried without escalating, and
- a **token saving** — one fewer round trip where an LLM reads a screen and reasons out a reply.

Raising coverage and cutting live token spend are therefore not two goals to trade off against each
other; they are one goal read two ways. This is why the reborn trainer can retire the old "never idle,
keep driving" appetite without losing the efficiency story: efficiency comes from the app *recognizing
and replaying the known cheaply*, not from an LLM grinding turns to keep a number climbing. The tokens
that matter are spent in the retrospective teaching moment (human-invoked), where one analysis can
author a rule that pays for itself across every future `app` replay of that screen.

# Reading, never driving

Coverage is a **read-only measurement** over the ledger, exactly like every other ledger consumer. It
counts rows by `actor` after the fact; it never chooses the next keystroke, never ranks a live action,
and never feeds a per-cycle selector. The number going up is a *description* of a session that
happened, not an *objective* a live loop optimizes toward — a metric wired back into live action
selection would be the self-driving anti-pattern the [trace ledger](/engine/trace-ledger.md) forbids.
The [priority engine](/architecture/rule-macro-engine.md) ranks and orders which taught behaviors run
or which suggestions the human sees; it does not, and coverage does not, let a computed score win over
an unrecognized screen. Recognition-and-stop always precedes any ranking.

# Examples

```
Ledger window (illustrative — reborn actor values):
{actor: "app",   session_id: "s-42", input: "158",   reward: {d_credits: 230}}
{actor: "app",   session_id: "s-42", input: "50"}
{actor: "app",   session_id: "s-42", input: "sell"}
{actor: "human", session_id: "s-42", input: "M4223"}      # app stopped on an unknown screen; operator drove

coverage = app / (app + human) = 3 / (3 + 1) = 75%
escalation frequency = human / (app + human) = 1 / 4 = 25%
live AI share = 0   (definitional — no live ai sender)

Teaching-provenance axis (separate): of the 8 guarded rules this world's app can play,
5 were AI-drafted-then-human-approved → AI teaching contribution = 5/8. This does NOT enter
the coverage ratio; all 8 fire as `app` when they run.
```

Read the same window two ways: **coverage** says the taught app carried 75% of the live keystrokes
this session; **token efficiency** says those same 3 `app` sends were 3 LLM turns not spent. The one
`human` row is the escalation — the learning moment where a macro could be recorded or the AI asked to
analyze after the fact, growing the repertoire so a similar screen counts toward `app` next time.

# Code divergence

The reborn metric above is the tip target. Archive / pre-reborn shapes remain
do-not-revive; tip measurement of the live share is **shipped**.

- **The old "autonomy ratio" formula and its 50% north-star (archive only).**
  `knowledge/architecture/autonomy-loop.md` defined `autonomy = trainer / (ai + trainer)`,
  **excluded** `human`, and framed "crossing 50%" as "flying itself." All three are
  retired: denominator is `app + human`, live `ai` is gone, and there is **no
  graduation threshold**. Do not revive `spectate_layout.format_autonomy_counts`
  (`App N / AI N · Hum N`).

- **Ledger live-sender enum — tip closed.** Tip `ledger.LedgerWriter.record_do`
  requires `actor ∈ VALID_SENDERS` (`app`|`human`); `session.VALID_SENDERS` matches.
  Legacy `{ai, trainer, human}` vocabulary is archive / old-row caution only.
  `ledger.live_actor_counts` counts only `app`/`human` and skips unknown/`ai` rows
  (never invents a third live driver).

- **Live coverage computation — tip shipped (WO-P5-072 / PWO-094 /
  WO-WIRE-COVERAGE-LEDGER-COUNTS).** `cockpit/covermeter.py` computes
  `app/(app+human)` (+ honest `?` for unavailable / empty window);
  `ledger.live_actor_counts` folds the ledger; `screens.py` wires the meter on
  the control strip. Queue claim "zero code exists" was stale.
  **Still prescribed, not built here:** the teaching-provenance axis (approved
  AI-drafted rules) and the session-retro candidate-mining surface — those stay
  with candidate-mining / the AI teacher, not this meter.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot and escalation target; the app
  plays back only taught screens and stops on the first unrecognized frame; the AI is a retrospective,
  human-invoked rule author and never a live keystroke; the priority layer ranks and orders taught
  behaviors and suggestions but never lets a computed score win over an unknown screen; retire the
  "never idle, keep driving" appetite.
- Operator rulings (RESOLVED 2026-07-23): the coverage meter shows App-vs-Human live share, with "AI"
  as a teaching-provenance axis whose live share is 0 — overriding the draft's three-way "APP vs AI vs
  Human" live meter.
- Project canon — the North Star three-actor model and its explicit retirement of the "autonomy ratio
  crosses 50% = flies itself" framing (see [north-star](/architecture/north-star.md)); the attribution
  substrate this metric counts (see [trace-ledger](/engine/trace-ledger.md)); the cockpit auto-% meter
  that renders it (see [trainer-cockpit](/surfaces/trainer-cockpit.md)); the priority/rule engine that
  ranks taught behaviors without overriding stop-on-unknown (see [rule-macro-engine](/architecture/rule-macro-engine.md)).
- Internal design history — the autonomy ratio and its token-efficiency identity (design history §15.1
  actor attribution, §19 autonomy ratio as the same axis as token efficiency), reimagined here from
  `knowledge/architecture/autonomy-loop.md` as coverage; the session-retro half of that doc is carried
  by candidate-mining / the AI teacher, not here.
- Code modules (plain-text): `ledger.py` (`VALID_SENDERS` + `live_actor_counts`);
  `cockpit/covermeter.py` (share math + `COV` meter); `screens.py` (control-strip
  wire); `session/session.py` (`VALID_SENDERS`). Teaching-provenance /
  session-retro remain with `miner.py` / AI-teacher surfaces, not this meter.
