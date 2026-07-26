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
| `record <manifest>` | Write a taught macro from an **already-captured** JSON demonstration manifest — daemon-free, never sends. Shipped shape (X6); see [Implementation status](#implementation-status) and [Macros](/engine/macros.md)'s Findings for how this differs from the live start/stop bracket capture this row originally specified. | `manifest` (path) `--draft` | `teach` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
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

# Implementation status (tip `13f34a8` + M3 WO-P2-G4 X1–X6 · live `./tw --help`)

**LIVE ops verbs today:** `status`, `ensure`, `screen`, `stop`, `do`, `send`, `read`, `history`,
`watch`, `attach`, `menumap`, `loops`, `record`.

`loops` (**G3**) landed as two slices — a read-only store reader/composer
(`tw2002_aiclient/loops/`), then the CLI wire. It is a **daemon-free read**: no protocol verb, no
socket, no `--run-dir`. Its only flag is canon's `--include-drafts`, and drafts stay tagged
`[DRAFT]` because they are inert until a human promotes them
([Candidate Mining](/engine/candidate-mining.md)). Exit code follows the read, not the row count:
an **unreadable** store exits **1** (a scripted caller must never read "no loops" out of a store
nobody could read); a **partial** read lists what it read, is marked INCOMPLETE, and exits 0. That
mapping is an implementation choice this concept does not yet rule on — it is recorded here, not
derived from canon.

`record` (**X6**) shipped as a **manifest writer, not the catalog's `{start,stop}` bracket
capture** above — canon had not caught up to a deliberate, disclosed, hub-Accepted shape
difference until this pass. It takes one positional `manifest` (a JSON document assembled by hand
or by script from real `tw do`/`tw screen --json` output — see `cmd_record`'s docstring for the
exact recipe) and `--draft` (write to `state/skills/_drafts/` instead of the blessed store);
daemon-free like `loops` above — no `--run-dir`, never opens a socket, never sends. Wiring a
*live* `tw attach` session directly into the recorder, so keystrokes become steps as they are
pressed, is real future work X6's own scope explicitly excluded, not a change of target — see
[Macros](/engine/macros.md)'s Findings for the mirrored note.

**NOT on tip as a `tw` CLI verb (HOLD / later / retired — do not document as shipped):**
`spectate` (**RETIRED / WONTBUILD** — Max `@ 13:13:55Z`; in-cockpit Spectate LIVE via PWO-055),
`start` (ensure covers spawn), `log`/`trail`, `frames`, `analyze`/`mine`, `replay`,
`play`/`haggle`/`autopilot`/`crawl`, `players`/`servers`/`probe`, `aiclient` as a separate curses
product entry (product is `./tw2002-aiclient`). `record` moved off this list into LIVE above —
X6 shipped it.

**WIRE-ONLY (a daemon protocol verb exists; no `tw` CLI subparser wraps it — not runnable from a
shell today, only over the daemon's own socket protocol):**

- **`state`** (**X1**, `protocol.py` `verb == "state"`) — the parsed current-sector read replay's
  start-anchor guard depends on. `WO-P2-G4-X1-STATE-SECTOR-READ` scoped a CLI wrapper as optional
  ("+ thin CLI if honesty requires") and none landed.
- **`autoloop_start` / `autoloop_stop` / `autoloop_status`** (**X4/X5**, `protocol.py`) — the
  background AUTO-LOOP player. **Not** the catalog's four-verb `{start,stop,pause,resume}`
  surface below: three wire verbs shipped, and `pause`/`resume` fall through to `unknown_verb` —
  argued down, not silently dropped (X4's own commit message: "Pause and resume are controls on a
  REPEATING loop; with one pass there is no cycle boundary to pause at, and a mid-macro pause is
  an indefinite hold on a half-executed transaction — a new safety surface with no contract and no
  rails"). Of the catalog row's key args, only `name` and `floor` are accepted
  (`autoloop.ARGS_AUTOLOOP_START`), and `floor` is genuinely **enforced** since X5 — a floored run
  halts fail-closed on `credits_unknown`/`credits_stale` rather than merely being remembered.
  `cycles`, `param`, and `force` are **refused** as `unsupported_arg`, never silently ignored — a
  caller asking for ten cycles and getting one would have been lied to by a surface that looked
  like it agreed. No `tw autoloop` CLI subparser exists at X4, X5, or X6; the catalog row states
  the full future target, this paragraph states wire-level reality today.

The catalog tables below are the **prescriptive full vocabulary** (target). Prefer this status
block when answering "what can I run right now?"

# Code Divergence

1. **Catalog vs tip help.** This concept still lists the full reborn/archive-derived verb set
   (including teach / App-drive / spectate). Tip `13f34a8` only ships the LIVE set above — honesty
   gate: never claim a HOLD or unported verb is runnable.

2. **Citations historically pointed at `twclient/cli.py`.** Authoritative tip parser is
   `tw2002_aiclient/session/cli.py` (ADR-001 relocate). Archive paths remain port-source for verbs
   not yet restored.

3. **`autopilot` is the reborn-vision tension to watch.** Under reborn canon the App is a
   **deterministic** autopilot that plays only taught, human-approved rules and **stops on any
   unknown screen** — it does not "reason." Documentation-only note — reconciliation is a separate
   work order; tip has no `tw autopilot` verb yet.

4. **`record`'s catalog row now documents a shape that was deliberately shipped different from
   what this concept originally specified.** X6's manifest writer (see Implementation status
   above) replaced the originally-catalogued live `{start,stop}` bracket capture as the *first*
   step, not the final one — the lane disclosed the gap and the hub Accepted it as an honest,
   correctly-scoped increment; live-attach capture is deferred, real future work, not abandoned
   target. This is this concept's first instance of DOCS WIN running in reverse: a genuinely
   Accepted shipped-shape difference that canon must catch up to, rather than code drifting from a
   canon that stayed right. `autoloop`'s wire-vs-CLI split (Implementation status above) and its
   `pause`/`resume` refusal are the same class of finding — recorded there rather than repeated
   here.

# Citations

[1] `tw2002_aiclient/session/cli.py` — `build_parser()`, tip authoritative LIVE verb list
[2] `canon/architecture/control-and-escalation.md` — actor model, approval gate, stop-on-unknown
[3] Archive `twclient/cli.py` — port-source for verbs not yet restored
[4] Project `CLAUDE.md` — hard rules / seat context
[5] `tw2002_aiclient/session/protocol.py` — `dispatch()`, the wire-verb chokepoint (`state`,
    `autoloop_start`/`_stop`/`_status`) and each verb's accepted/refused argument set
[6] `tw2002_aiclient/session/autoloop.py` — `ARGS_AUTOLOOP_START`, the X4/X5 refusal reasoning for
    `cycles`/`param`/`force`/`pause`/`resume`
[7] `tw2002_aiclient/loops/recorder.py` + `cmd_record` (`tw2002_aiclient/session/cli.py`) — the X6
    manifest-based recorder's real shape
