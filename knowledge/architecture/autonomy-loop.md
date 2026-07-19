---
type: System
title: Autonomy Loop — Actor Attribution, the Autonomy Ratio, and Session Retro
description: Every keystroke is attributed to who or what generated it, feeding a graduation gauge and a retro tool that mines a session for AI decisions worth codifying.
tags: [autonomy, ledger, metric, session-retro, prescriptive]
timestamp: 2026-07-19T16:12:01Z
---

The autonomy loop is the measurement layer of the trainer: it attributes every keystroke to its
source, derives a single headline gauge from that attribution, and closes the loop by mining a
completed session for the AI decisions that recurred profitably enough to deserve becoming a
permanent, deterministic trainer behavior. This concept is prescriptive — it specifies the
additive ledger fields and the tools that read them, not a report that the fields already exist
in every ledger entry.

# Actor Attribution

Every action funnels through one ledger choke-point, and every entry there carries an `actor`.

# Schema

Additive fields on each ledger entry (alongside its existing prompt/input/pre-state/post-state/
reward fields — see [the session engine](/architecture/session-engine.md) for the ledger's base
shape):

| Field | Type | Notes |
|---|---|---|
| `actor` | enum `{ai, trainer, human}` | `ai` — an LLM-decided send. `trainer` — a deterministic, no-LLM engine send (loop replay, mining, haggling, or any other rules-based engine). `human` — a keystroke typed directly by the operator in an interactive session. |
| `session_id` | string | Correlates a run of ledger entries to one continuous play session (and to that session's own transcript log), making "a session" a queryable unit rather than an arbitrary slice of one unbroken ledger stream. |
| `intent` | string, optional | A short AI-supplied rationale for a `tw do`, e.g. "selling organics, port buys above average." Optional and cheap; the ledger otherwise captures *what* happened and *what it earned*, not *why* it was chosen — the reasoning is what makes a recurring decision recognizable as a pattern. |

# The Autonomy Ratio

The gauge: **autonomy = trainer / (ai + trainer)**, computed over a rolling window of ledger
entries. `human` entries are excluded from the ratio itself — a human driving directly is the
operator steering, not a contest between the AI and the trainer — but all three counts are shown
alongside it for context.

As learned loops replace AI-driven decisions, `ai` count falls and `trainer` count rises, so the
ratio climbs toward and past a majority share. Crossing 50% is the trainer's concrete definition
of "flying itself" — see [the trainer vision](/architecture/trainer-vision.md) for why this
specific crossing is the north-star milestone rather than an arbitrary number.

# Session Retro

The learning loop's back half: after a session, the goal is to find "what did the AI do
repeatedly and profitably that should be coded into the trainer instead of re-reasoned every
time." A retro tool reads one session's ledger slice (via `session_id`), groups the `actor=ai`
entries by pattern, ranks the groups by profit and frequency, and surfaces the recurring
profitable ones as codification candidates — the same shape of signal the profit-miner already
applies to raw keystroke sequences, but filtered to the AI-driven decisions specifically, since
those are the ones a human or an AI author would want to turn into a permanent trainer behavior.

# Examples

```
Ledger entries (illustrative):
{ts: ..., actor: "ai",      session_id: "s-42", input: "sell", reward: {d_credits: 230}}
{ts: ..., actor: "trainer", session_id: "s-42", input: "158",  reward: {d_credits: 340}}
{ts: ..., actor: "human",   session_id: "s-42", input: "M4223"}

Autonomy ratio over this window = trainer / (ai + trainer) = 1 / (1 + 1) = 50%.

Session retro on s-42 groups the actor=ai entries and flags "sell at this port pair, ~230cr
per action, recurs 6x this session" as a codification candidate.
```

# Citations

[1] design history §15.1 (actor attribution and the autonomy ratio)
[2] design history §15.6 (session-retro logging and the retro tool)
[3] design history §15.0 (actor attribution as one field, two payoffs)
[4] design history §19 (autonomy ratio as the same axis as token efficiency)
