---
type: Reference
title: CLI Verb Surface — the tw Vocabulary
description: The single catalog of every one-shot tw verb — its effect, key arguments, actor-class, and owning concept — anchored to the human-approval gate and the stop-on-unknown escalation.
tags: [architecture, cli, verbs, reference, control]
timestamp: 2026-07-24T22:07:00Z
---

`tw` is the stateless one-shot CLI a Bash-driving caller — a human at a shell, a script, or the
App autopilot — invokes to act on the ONE live game session. Each invocation is a single round
trip against the daemon (`twd`) and exits; the daemon owns the persistent telnet connection and the
pyte-emulated terminal. This concept is the **catalog of every `tw` verb**: what each does, its
load-bearing arguments, which control-class it belongs to, and the concept that owns its behavior.

It does not specify the round-trip mechanics or the settle detection those verbs depend on — those
belong to [the Session Engine](/architecture/session-engine.md) — nor the control-flow rules that
constrain what any verb may do — those belong to
[Control & Escalation](/architecture/control-and-escalation.md). This is the surface vocabulary
layered over both.

# The One-Round-Trip Contract

Every ordinary verb shares one shape, owned by [the Session Engine](/architecture/session-engine.md)
and not restated here: **connect to the daemon's unix socket → send one JSON request → read one
JSON line back (a settled screen, or a typed result) → disconnect.** The caller never holds a
socket open, so a Bash-driving actor issues one verb, gets a settled screen, and reasons about it
before the next. `settled_reason` on the returned screen is the settle engine reporting *why* it
judged the screen done.

Three carve-outs to the one-shot shape, all deliberate:

- **Streaming / long-lived surfaces** hold the socket open rather than round-trip-and-exit:
  `watch` subscribes to the settle-edge push stream until `--frames N` or Ctrl-C; `spectate`,
  `attach`, and `aiclient` are long-running curses/TUI sessions, not one-shots.
- **Daemon-free reads** never touch the socket at all — they read on-disk artifacts directly, so
  they work with the daemon stopped: `log`/`trail` (reads `state/ledger.jsonl`), `frames` (reads
  `state/frames/`), `analyze` and `mine` (read the ledger), `loops`/`menumap`/`players`/`servers`
  (read their own stores/catalogs). `probe` opens its own throwaway connections to *catalog*
  endpoints, never the live game session.
- **Session-establishing verbs** (`start`, `ensure`) may spawn the daemon before the round trip.

# Actor Classes

Every verb falls into exactly one of three classes. This is the reborn control model
([Control & Escalation](/architecture/control-and-escalation.md)) projected onto the CLI: **live
keystroke senders are `{app, human}` only — never the AI.**

- **`drives {app,human}`** — the verb can take the control lock and emit a live keystroke into the
  game session. The two legal senders are the **App** (deterministic autopilot / macro playback)
  and the **Human** (sovereign pilot). Sub-labels sharpen *which* sender a verb serves: `{human}`
  for the interactive keyboard (`attach`), `{app}` for the deterministic macro/loop/pilot drivers
  (`play`, `replay`, `autoloop`, `autopilot`, `haggle`, `crawl`). The bare primitives
  (`do`, `send`, `ensure`, `start`, `stop`) are `{app,human}` — usable by either legal sender.
- **`read-only`** — never takes the control lock, never sends a keystroke. Safe to observe with.
- **`teach`** — the retrospective, human-invoked teach path. Reads history and *proposes* rules or
  macros; it never sends a live keystroke and never auto-applies its own output. `record`,
  `analyze`, and `mine`/`patterns` are the teach verbs.

There is no `ai` actor-class, because the AI is never a live driver — it authors drafts that a
human must approve before the App can ever play them.

## Read-only-safe at any time vs. control-lock

A caller may run the pure observers — **`status`, `screen`, `state`, `history`, `spectate`,
`watch`, `log`/`trail`, `frames`, `loops`, `menumap`, `servers`, `players`** — at **any** moment,
including while the App or a human is mid-drive, because none of them touch the control lock. The
`drives {*}` verbs contend for that lock; the control-lock arbitration (who may hold it, and the
handoff on escalation) is specified in
[Control & Escalation](/architecture/control-and-escalation.md), not here.

# The Hard Rule

**No verb bypasses the human-approval gate or stop-on-unknown.** A verb can send a keystroke only
as the App playing an already-**human-approved** rule, or as the Human's own input. Nothing on this
surface — not `autopilot start`, not `play`, not `replay`, not `autoloop` — lets an AI-authored,
unapproved rule fire, and nothing lets the App guess past a screen it cannot match: on an
unrecognized screen the App **stops and hands the keyboard to the Human**. Both invariants are owned
by [Control & Escalation](/architecture/control-and-escalation.md); the CLI merely exposes verbs
that obey them.

# Schema

The authoritative verb list is `twclient/cli.py`'s `build_parser()` — this table is derived from it
(README/DESIGN drift is recorded under [Code Divergence](#code-divergence) below). Key args lists
only the load-bearing flags; `--json` (machine output) and `--run-dir PATH` (target a non-default
daemon socket) are available on essentially every verb and are omitted for brevity.

## Daily-driver verbs

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `start` | Spawn the daemon, connect, negotiate, return the first settled screen. | `--host` `--port` `--name` `--timeout` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |
| `do "<input>"` | **Primary verb.** Send input, wait until settled, return the new screen + `settled_reason`. | `--wait-prompt REGEX` `--secret` `--no-enter` `--timeout` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |
| `screen` | Current settled screen, prompt, classification — non-destructive. | `--compact` `--raw` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `status` | Daemon alive? connected? idle-ms? classification? `--json` adds `autopilot` + `intervention{needs_attention}`. | — | `read-only` | [Control & Escalation](/architecture/control-and-escalation.md) |
| `stop` | Graceful in-game QUIT → disconnect → daemon exit. | — | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |

## Session primitives

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `send "<input>"` | Raw send, no wait (rare / low-level). | `--secret` `--no-enter` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |
| `read` | Wait-and-return WITHOUT sending — for unsolicited server output. | `--wait-prompt REGEX` `--timeout` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `state` | Parsed structured game-state only (sector/credits/turns/port…). | — | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `history` | Recent screens/commands (full transcript lives in `logs/`). | `--n N` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `ensure [target]` | Idempotent auto-login: classify → no-op if already at `target`, else register/log in to it, spawning the daemon first if needed. | `--profile NAME` (required) `--timeout` `--no-auto-arm` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |

## Read-only introspection

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `watch` | Tail the settle-edge push stream (holds the socket; exits on `--frames`/Ctrl-C). | `--frames N` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `log` (alias `trail`) | Human-readable per-action trail — QUESTION → KEYSTROKE → RESULT (reads `state/ledger.jsonl`; no daemon). | `--n N` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `frames {tail,show,grep,diff}` | Post-mortem over full 80×25 settle frames in `state/frames/` (no daemon). | `--session ID` `-n N` `seq` `pattern` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `menumap` | Read-only menu-map inspector — coverage, orphans, you-are-here ★ / off-map (never sends). | `--profile` \| `--world-id` \| `--path` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `loops` | List every learned loop with profit metadata — CLI twin of the in-TUI Learned-Loops Library. | `--include-drafts` | `read-only` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `players {list,add,next}` | Multi-character rotation bank (reads/writes `state/player_bank.json`; no daemon, no game keystrokes). | `add <profile>` `--note k=v` `next --current` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `servers list` | Print the `config/servers.toml` catalog (no live connection). | — | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `probe [server]` | Read-only catalog probe: IAC-only (L0), optional `--menu` peeks the TWGS game list; connects to catalog endpoints, not the live session. | `--all` `--menu` `--write-catalog` | `read-only` | [Session Engine](/architecture/session-engine.md) |

## Teach (retrospective, human-invoked)

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `record {start,stop}` | Bracket a named skill capture — every `do` sent while open becomes a step; `stop` saves a replayable skill. | `name` (start) | `teach` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `analyze <session>` | Session-retro: group recurring ledger decisions, rank profitable ones as candidates to codify (proposes, never applies). | `--min-support` `--top` | `teach` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `mine` (alias `patterns`) | Mine the Trace-Ledger for recurring profitable input-subsequences; proposes drafts under `state/skills/_drafts/`. | `--min-support` | `teach` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |

## App-drive (deterministic macro / loop / pilot playback)

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `replay <name>` | Re-issue a saved skill's steps, halting on the first divergence from what was recorded/mined. | `--param k=v` `--step-timeout` `--force` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `play <name>` | Run a learned skill for N cycles synchronously; halts on surprise or a rail (`--cycles`/`--floor`). | `--cycles` `--floor` `--param k=v` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `autoloop {start,stop,pause,resume}` | Drive the background AUTO-LOOP player; `start` returns immediately (watch progress via `spectate`/`watch`). | `name` `--cycles` `--floor` `--param k=v` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `haggle` | Deterministic auto-haggle (NO LLM) for the port OFFER sub-dialogue the session must already sit at. | `--fair-value` `--accept-threshold-pct` `--round-cap` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `autopilot {preview,start,stop}` | Autonomous goal-orchestrator; `preview` is a safe dry-run (never sends), `start`/`stop` arm/halt the background driver. | `--profile` `--max-ticks` `--cash-floor` | `drives {app}` (preview: `read-only`) | [Priority Engine](/engine/priority-engine.md) |
| `crawl` | Drive a hub-supervised menu crawl against a `crawl_sacrificial` profile's world (refused for opt-out profiles). | `--profile` (required) `--max-nodes` `--path` | `drives {app}` | [Session Engine](/architecture/session-engine.md) |

## Human-facing surfaces

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `spectate` | Ops read-only curses HUD over the running daemon, decoupled from whoever drives (`--snapshot` for scripting). | `--snapshot` `--frames` | `read-only` | [Trainer UI](/surfaces/trainer-ui.md) |
| `attach` | Interactive live console — take the keyboard and play by hand; Ctrl-] hands control back. | — | `drives {human}` | [Trainer UI](/surfaces/trainer-ui.md) |
| `aiclient` | Product TUI — profile launcher, create form, Autopilot ON/OFF (same as `./tw2002-aiclient`). | — | `drives {app,human}` | [Trainer UI](/surfaces/trainer-ui.md) |

# Examples

The daily one-shot rhythm — one verb, one settled screen, then reason:

```
tw ensure --profile pilot          # land at the command prompt (idempotent)
tw screen                          # look — non-destructive, safe any time
tw do "d"                          # send 'd', wait for settle, get the new screen
tw status --json                   # intervention.needs_attention? still mine to drive?
```

Observe a live drive without touching the lock (a second terminal, App or human driving):

```
tw spectate                        # read-only HUD, contends for nothing
tw watch --frames 5                # capture 5 settle-edge events into a transcript
tw log --n 20                      # the QUESTION → KEYSTROKE → RESULT trail, daemon or not
```

Teach after an escalation (retrospective, proposes — never fires):

```
tw analyze all --top 10            # rank recurring decisions worth codifying
tw mine --min-support 3            # propose draft skills from the ledger
# a human reviews and approves before anything the App plays back can ever fire
```

# Implementation status (tip `8f03289` · live `./tw --help`)

**LIVE ops verbs today:** `status`, `ensure`, `screen`, `stop`, `do`, `send`, `read`, `history`,
`watch`, `attach`, `menumap`.

**NOT on tip (HOLD / later phases — do not document as shipped):** `spectate` (**F2 HOLD**),
`loops` / `autoloop` (**G2–G4 HOLD**), `start` (ensure covers spawn), `log`/`trail`, `frames`,
`analyze`/`mine`, `record`/`replay`, `play`/`haggle`/`autopilot`/`crawl`, `players`/`servers`/`probe`,
`aiclient` as a separate curses product entry (product is `./tw2002-aiclient`).

The catalog tables below are the **prescriptive full vocabulary** (target). Prefer this status
block when answering "what can I run right now?"

# Code Divergence

1. **Catalog vs tip help.** This concept still lists the full reborn/archive-derived verb set
   (including teach / App-drive / spectate). Tip `8f03289` only ships the LIVE set above — honesty
   gate: never claim a HOLD or unported verb is runnable.

2. **Citations historically pointed at `twclient/cli.py`.** Authoritative tip parser is
   `tw2002_aiclient/session/cli.py` (ADR-001 relocate). Archive paths remain port-source for verbs
   not yet restored.

3. **`autopilot` is the reborn-vision tension to watch.** Under reborn canon the App is a
   **deterministic** autopilot that plays only taught, human-approved rules and **stops on any
   unknown screen** — it does not "reason." Documentation-only note — reconciliation is a separate
   work order; tip has no `tw autopilot` verb yet.

# Citations

[1] `tw2002_aiclient/session/cli.py` — `build_parser()`, tip authoritative LIVE verb list
[2] `canon/architecture/control-and-escalation.md` — actor model, approval gate, stop-on-unknown
[3] Archive `twclient/cli.py` — port-source for verbs not yet restored
[4] Project `CLAUDE.md` — hard rules / seat context
