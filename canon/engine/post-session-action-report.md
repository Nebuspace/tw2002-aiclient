---
type: System
title: Post-Session Action Report — Accountability for Autonomous App Action
description: A pull-based digest of a session's actor=app dispatches from the trace ledger — the accountability mechanism DECISIONS.md substitutes for live per-firing approval once a taught rule is armed to fire the app layer autonomously.
tags: [accountability, trace-ledger, post-session, app-actor, reporting, stub, prescriptive]
timestamp: 2026-08-07T00:00:00Z
---

**Status: stub.** This is a discoverability pointer, not a from-scratch concept — the substance is
authored in [trace-ledger § Passive substrate](/engine/trace-ledger.md#passive-substrate-it-never-decides)
(fifth-consumer bullet) and [trace-ledger § Code divergence](/engine/trace-ledger.md#code-divergence)
(the `interrupted_by_human` consumption note). Where this stub and trace-ledger's prose
disagree, trace-ledger wins — this file exists so the report has its own entry in
[canon/index.md](/index.md) rather than living only as a bullet inside a different concept's page.

# Why this exists

`canon/DECISIONS.md` — **six-archived-modules-reroute-vs-fight-ev** (hub 2026-08-05, Max direct
clarification) — rules that the `app` layer (the deterministic, taught/armed autopilot) may execute
a human-approved rule's action programmatically, including firing against another human, once that
rule is human-approved at teach/arm time. That does **not** relax `AI never live-drives`: the
AI/LLM teacher still never reasons over the next live keystroke (zero AI reasoning per cycle,
`north-star.md`). What changes is that `app` autonomy is real and growing, and the accountability
model for it is explicitly **not** per-firing human approval — Max: *"The human learns by watching
the action and then later by the report [...] provided post-session of what happened."* The gate
that keeps this safe stays at **teach time** (a rule is human-approved before it can ever fire); the
post-session report is how the human audits what an already-armed rule actually did, after the fact.

See `canon/DECISIONS.md` — **post-session-action-report** entry — for the ruling this stub
documents; that entry records the report as **CLOSED / SHIPPED on tip** as of 2026-08-06.

# What it is

A pull-based, daemon-free digest built by reading the trace ledger (`canon/engine/trace-ledger.md`)
for a session and filtering to `actor=app` rows — the same digest [coverage
metrics](/engine/coverage-metrics.md) counts, presented as a human-readable trail instead of a
ratio. It is a **read**, never a decision input: nothing in this repo re-reads the report to choose
a live keystroke, which would recreate the self-driving loop the trace-ledger concept explicitly
forbids.

**Delivery surface (as shipped):** CLI verb `tw report` (`tw2002_aiclient/session_report.py`,
`tw2002_aiclient/session/cli.py: cmd_report`). Daemon-free — reads `state/ledger.jsonl` directly.
Not yet cataloged in [CLI Verb Surface](/architecture/cli-verbs.md) — a residual doc gap, not a
missing capability.

# Fields (as built — `session_report.py`)

The report (`SessionReport`) surfaces, per invocation:

- **`ledger_path`** — which ledger file was read.
- **`session_id`** — narrows to one session when passed; unset reads the whole ledger and, if more
  than one session appears in the window, adds a note telling the operator to narrow with
  `--session-id`.
- **`app_actions`** — the chronological list of `actor=app` dispatch rows, each an `AppActionRow`:
  - `ts` — dispatch timestamp
  - `screen` — the settled screen class the rule fired against
  - `rule_id` — the taught rule's id (falls back to the `intent` field if `rule_id` is absent)
  - `target_player` — set only when the action targeted another player (the PvP-visibility case
    the accountability model exists for)
  - `input_summary` — the keystroke(s) sent, redacted (`<redacted>`) if the dispatch was a secret
    send, `"Enter (default)"` for a blank/default-accept send, truncated past 40 chars
  - `session_id`
- **`human_count`** — how many `actor=human` rows matched the same filter, for at-a-glance
  comparison against the app-action count.
- **`skipped_interrupted`** — how many `app` rows were excluded because `interrupted_by_human` was
  set (a `tw attach` seized the control lock mid-dispatch, corrupting that row's action→outcome
  mapping); `tw report --include-interrupted` opts them back in.
- **`notes`** — free-text advisories (currently: the multi-session-in-window note above).

`tw report --out <path>` writes the same formatted text as a file artifact; `--json` emits the
equivalent structured payload instead of the plain-text trail.

# What it is not

- Not a gate. Nothing blocks on the report existing or being read — it is retrospective, never a
  precondition for a rule firing.
- Not a live-decision input. `build_session_report` only reads the ledger; it never writes to it
  and is never called from the dispatch path.
- Not a replacement for the teach-time human-approval gate ([control-and-escalation](/architecture/control-and-escalation.md)) — post-session accountability and teach-time approval are two
  different invariants that both hold simultaneously, not a trade of one for the other.
- Not yet an unprompted session-end auto-print. Today's primary surface is the on-demand `tw report`
  pull; an automatic print/summary at session exit is optional delivery polish, not ruled out but
  not built.

# Citations

- `canon/DECISIONS.md` — **six-archived-modules-reroute-vs-fight-ev** (Correction, hub 2026-08-05)
  and **post-session-action-report** (CLOSED / SHIPPED, 2026-08-06) entries — the rulings this stub
  documents.
- [trace-ledger § Passive substrate](/engine/trace-ledger.md#passive-substrate-it-never-decides) —
  the fifth-consumer bullet naming this report; canonical detail lives there.
- [trace-ledger § Code divergence](/engine/trace-ledger.md#code-divergence) — the
  `interrupted_by_human` consumption note.
- [coverage-metrics](/engine/coverage-metrics.md) — the sibling consumer counting the same
  `actor=app` rows as a ratio rather than a trail.
- `tw2002_aiclient/session_report.py`, `tw2002_aiclient/session/cli.py: cmd_report` — the shipped
  implementation this stub describes honestly (no unbuilt fields invented).
