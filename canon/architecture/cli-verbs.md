---
type: Reference
title: CLI Verb Surface — the tw Vocabulary
description: The single catalog of every one-shot tw verb — its effect, key arguments, actor-class, and owning concept — anchored to the human-approval gate and the stop-on-unknown escalation.
tags: [architecture, cli, verbs, reference, control]
timestamp: 2026-08-06T01:28:00Z
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
  they work with the daemon stopped. **LIVE today:** `log`/`trail`/`report` (ledger),
  `loops`/`menumap`/`pairs`/`chains`/`record`/`teach`/`skill`/`reflex`/`rule` (stores),
  `servers`/`probe` (catalog), `players` (rotation metadata), `mine`/`patterns` (candidate mining),
  `coach`, `port-floor`, `planet-colonization`, `frames` (post-mortem settle frames under
  `state/frames/` — daemon write via `FrameRecorder`; CLI read path filesystem-only).
  `probe` opens its own throwaway connections to *catalog* endpoints, never the live game session.
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
  `teach analyze`, `skill approve`, and `mine`/`patterns` are the teach verbs.

There is no `ai` actor-class, because the AI is never a live driver — it authors drafts that a
human must approve before the App can ever play them.

## Read-only-safe at any time vs. control-lock

A caller may run the pure observers — **`status`, `screen`, `history`,
`watch`, `log`/`trail`, `frames`, `loops`, `menumap`, `pairs`, `servers`, `players`** — at **any** moment,
including while the App or a human is mid-drive, because none of them touch the control lock. The
`drives {*}` verbs contend for that lock; the control-lock arbitration (who may hold it, and the
handoff on escalation) is specified in
[Control & Escalation](/architecture/control-and-escalation.md), not here.

`state` is **not** a `tw` CLI verb (WIRE-ONLY today — daemon protocol only, no `tw state`
subparser; see the Session primitives table below) and `spectate` is **RETIRED / WONTBUILD as
`tw spectate`** (Max) — the read-only Spectate surface lives in-cockpit instead (see
[Spectate & Attach](/surfaces/spectate-and-attach.md)). Neither belongs on this "runnable at any
moment" list of actual `tw` subcommands.

# The Hard Rule

**No verb bypasses the human-approval gate or stop-on-unknown.** A verb can send a keystroke only
as the App playing an already-**human-approved** rule, or as the Human's own input. Nothing on this
surface — not `autopilot start`, not `play`, not `replay`, not `autoloop` — lets an AI-authored,
unapproved rule fire, and nothing lets the App guess past a screen it cannot match: on an
unrecognized screen the App **stops and hands the keyboard to the Human**. Both invariants are owned
by [Control & Escalation](/architecture/control-and-escalation.md); the CLI merely exposes verbs
that obey them.

# Schema

The authoritative LIVE verb list is `tw2002_aiclient/session/cli.py`'s `build_parser()` (ADR-001) —
run `./tw --help` for tip truth. The catalog tables that follow are the **prescriptive TARGET
vocabulary** (what the surface is allowed to grow into). Prefer
**Implementation status** below when answering "what can I run
right now?" — never treat a TARGET-only row as a shipped `tw` subcommand.
(README/DESIGN drift is recorded under [Code Divergence](#code-divergence) below). Key args lists
only the load-bearing flags; `--json` (machine output) and `--run-dir PATH` (target a non-default
daemon socket) are available on essentially every verb and are omitted for brevity.
**Footgun:** `TW_CONFIG_DIR` isolates config only — it does **not** move the daemon socket.
`status` / `stop` / `ensure` without `--run-dir` (and without `TW_RUN_DIR`) **fail closed** when
config is isolated, and print the run-dir path they would have targeted (WO-CLI-RUN-DIR-FOOTGUN-WARN).

## Daily-driver verbs

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `start` | **TARGET as `tw start`** (ensure covers spawn on tip). Spawn the daemon, connect, negotiate, return the first settled screen. | `--host` `--port` `--name` `--timeout` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |
| `do "<input>"` | **Primary verb.** Send input, wait until settled, return the new screen + `settled_reason`. | `--wait-prompt REGEX` `--secret` `--no-enter` `--timeout` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |
| `screen` | Current settled screen, prompt, classification — non-destructive. | `--compact` `--raw` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `status` | Daemon alive? connected? idle-ms? classification? `--json` adds `autopilot` + `intervention{needs_attention}`. | — | `read-only` | [Control & Escalation](/architecture/control-and-escalation.md) |
| `stop` | Graceful in-game QUIT → disconnect → daemon exit. | — | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |

## Session primitives

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `send "<input>"` | Raw send, no wait (rare / low-level). | `--secret` `--no-enter` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |
| `read` | Wait-and-return WITHOUT sending — for unsolicited server output. | `--wait-prompt REGEX` `--timeout` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `state` | **WIRE-ONLY today** (daemon protocol; no `tw state` subparser). Parsed structured game-state only (sector/credits/turns/port…). | — | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `history` | Recent screens/commands (full transcript lives in `logs/`). | `--n N` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `ensure [target]` | Idempotent auto-login: classify → no-op if already at `target`, else register/log in to it, spawning the daemon first if needed. | `--profile NAME` (required) `--timeout` `--no-auto-arm` | `drives {app,human}` | [Session Engine](/architecture/session-engine.md) |

## Read-only introspection

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `watch` | Tail the settle-edge push stream (holds the socket; exits on `--frames`/Ctrl-C). | `--frames N` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `log` (alias `trail`) | Human-readable per-action trail — QUESTION → KEYSTROKE → RESULT (reads `state/ledger.jsonl`; no daemon). | `--n N` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `report` | Post-session `actor=app` action digest from the trace ledger — the accountability trail for an already-armed rule's autonomous firing, never a live-decision input (reads `state/ledger.jsonl`; no daemon). | `--ledger PATH` `--session-id ID` `--world-id SLUG` `--out PATH` `--include-interrupted` | `read-only` | [Post-Session Action Report](/engine/post-session-action-report.md) |
| `frames {tail,show,grep,diff}` | **LIVE** — post-mortem over full 80×25 settle frames in `state/frames/` (daemon write via `FrameRecorder` on settle; read path filesystem-only, no daemon). | `--session ID` `-n N` `seq` `pattern` `--state-dir` `--json` | `read-only` | [Session Engine](/architecture/session-engine.md) · [Trace Ledger](/engine/trace-ledger.md) |
| `menumap` | Read-only menu-map inspector — coverage, orphans, you-are-here ★ / off-map (never sends). | `--profile` \| `--world-id` \| `--path` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `loops` | List every learned loop with profit metadata — CLI twin of the in-TUI Learned-Loops Library. | `--include-drafts` | `read-only` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `pairs` | List class-derived DISCOVERED pair loops for a world — margin-unknown candidates, never the taught `L)chains` library (reads `state/world/<world-id>` directly, never sends). | `--world-id` (required) `--json` | `read-only` | [Trade Loops](/strategy/trade-loops.md) |
| `players {list,next,rotate}` | **LIVE.** Multi-character rotation bank metadata (reads `state/player_bank.json`; no daemon, no game keystrokes). `list` prints bank rows + no-collusion boundary; `next` prints the next eligible profile; `rotate` prints the rotation driver's decision with reasoning. | `--cooldown-hours H` on each subverb | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `servers list` | Summarize `config/servers.inventory.json` provenance + optional liveness sidecar (no live session). | `--inventory` `--liveness` `--json` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `probe` | TCP-only catalog probe (no login / no turns); writes `config/servers.liveness.json`. Same engine as `scripts/catalog-tcp-probe.py`. | `--limit` `--timeout` `--out` `--json` | `read-only` | [Session Engine](/architecture/session-engine.md) |
| `coach show [id]` | **LIVE.** Show one strategy card in full, or list all cards when `id` is omitted (daemon-free). | `id` (optional) | `read-only` | [Coaching Engine](/engine/coaching-engine.md) |
| `port-floor {snapshot,analyze}` | **LIVE.** Observation-store ingest + regrowth/floor analysis over world-model sector JSON (daemon-free; never sends). | `snapshot` / `analyze` args per `--help` | `read-only` | [Port Economics](/strategy/port-economics.md) |
| `planet-colonization {snapshot,analyze}` | **LIVE.** Observation-store ingest + production-hypothesis analysis over planet record JSON (daemon-free; never sends). | `snapshot` / `analyze` args per `--help` | `read-only` | [Planet Colonization](/strategy/planet-colonization.md) |

## Teach (retrospective, human-invoked)

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `record <manifest>` | **LIVE.** Write a taught macro from an **already-captured** JSON demonstration manifest — daemon-free, never sends. Shipped shape (X6); see Implementation status and [Macros](/engine/macros.md)'s Findings for how this differs from the live start/stop bracket capture this row originally specified. | `manifest` (path) `--draft` | `teach` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `teach analyze` | **LIVE.** On-demand AI teacher: read recent ledger + a frame source, propose an inert rule draft (never approves, never sends). Wired by `teach_cli.add_teach_parser`. Default backend always declines until a model is wired. | `--session ID` `--ledger PATH` `--frame-file PATH` `--backend MODULE:FUNC` `--state-dir PATH` `--json` | `teach` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `mine` (alias `patterns`) | **LIVE.** Mine the Trace-Ledger for recurring profitable input-subsequences; proposes inert drafts under `state/skills/_drafts/`. Flag is `--top-k` (not `--top`). | `--min-support` `--top-k` `--ledger` `--drafts` `--no-propose` `--json` | `teach` | [Candidate Mining](/engine/candidate-mining.md) · [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `skill approve <name>` | **LIVE.** Promote one mined/AI skill draft from `state/skills/_drafts/` into the blessed skills library — filesystem-only; never sends. The human act (mirrors `tw rule approve`). Wired by `skill_cli.add_skill_parser`. | `name` `--world-id SLUG` `--json` | `teach` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) · [Candidate Mining](/engine/candidate-mining.md) |

## App-drive (deterministic macro / loop / pilot playback) — TARGET unless noted

Most of these rows are still not `tw` CLI subparsers (Option B · WO-ESCALATE-CLI-VERBS).
Autoloop *wire* verbs exist on the daemon socket — see Implementation status — but there is no
`tw autoloop` / `tw play` / `tw haggle` / `tw autopilot` / `tw crawl` / `tw replay` shell entry.
**Exception on tip:** `tw chain` (discovered trade-chain driver) is LIVE — see row below.

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `chain {start,stop,status}` | **LIVE.** Start/stop/status a discovered trade chain (start requires a human-confirmed fingerprint). Distinct from read-only `tw chains` / `tw pairs`. | per-subverb; see `tw chain --help` | `drives {app}` | [Trade Loops](/strategy/trade-loops.md) · ADR-003 |
| `replay <name>` | **TARGET.** Re-issue a saved skill's steps, halting on the first divergence from what was recorded/mined. | `--param k=v` `--step-timeout` `--force` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `play <name>` | **TARGET.** Run a learned skill for N cycles synchronously; halts on surprise or a rail (`--cycles`/`--floor`). | `--cycles` `--floor` `--param k=v` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `autoloop {start,stop,pause,resume}` | **TARGET as `tw` CLI.** Wire verbs `autoloop_*` exist (see Implementation status); no shell subparser. Catalog `{resume}` deliberately does not match wire (`relaunch` instead of thaw). | `name` `--cycles` `--floor` `--param k=v` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `haggle` | **TARGET.** Deterministic auto-haggle (NO LLM) for the port OFFER sub-dialogue the session must already sit at. Engine code may exist; not exposed as `tw haggle`. | `--fair-value` `--accept-threshold-pct` `--round-cap` | `drives {app}` | [Rule–Macro Engine](/architecture/rule-macro-engine.md) |
| `autopilot {preview,start,stop}` | **TARGET.** Autonomous goal-orchestrator; `preview` is a safe dry-run (never sends), `start`/`stop` arm/halt the background driver. Tip has no `tw autopilot`. | `--profile` `--max-ticks` `--cash-floor` | `drives {app}` (preview: `read-only`) | [Priority Engine](/engine/priority-engine.md) |
| `crawl` | **TARGET.** Drive a hub-supervised menu crawl against a `crawl_sacrificial` profile's world (refused for opt-out profiles). | `--profile` (required) `--max-nodes` `--path` | `drives {app}` | [Session Engine](/architecture/session-engine.md) |

## Human-facing surfaces

| verb | one-line effect | key args | actor-class | owning concept |
|---|---|---|---|---|
| `spectate` | **RETIRED / WONTBUILD as `tw spectate`** (Max). Ops read-only curses HUD — in-cockpit Spectate is the live surface. | `--snapshot` `--frames` | `read-only` | [Spectate & Attach](/surfaces/spectate-and-attach.md) |
| `attach` | **LIVE.** Interactive live console — take the keyboard and play by hand; Ctrl-] hands control back. | — | `drives {human}` | [Spectate & Attach](/surfaces/spectate-and-attach.md) |
| `aiclient` | **Not a `tw` subcommand** — product TUI is `./tw2002-aiclient` / `python -m tw2002_aiclient`. | — | `drives {app,human}` | [Entry & Profile Selection](/surfaces/entry-and-profile-selection.md) → [The Trainer Cockpit](/surfaces/trainer-cockpit.md) |

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
tw watch --frames 5                # capture 5 settle-edge events into a transcript
tw log --n 20                      # the QUESTION → KEYSTROKE → RESULT trail, daemon or not
# spectate: in-cockpit only (no tw spectate — RETIRED)
```

Teach after an escalation (retrospective, proposes — never fires). LIVE today:

```
tw teach analyze --frame-file ./frame.json   # propose an inert draft (backend may decline)
tw mine --min-support 3 --top-k 10           # ledger mining → state/skills/_drafts/
tw skill approve <draft-name>                # human promotes one draft into blessed store
tw reflex                                    # what the blessed library proposes for the live screen
tw rule …                                    # draft / approve path (see tw rule --help)
# a human reviews and approves before anything the App plays back can ever fire
```

# Implementation status (tip `f14cc30` · live `./tw --help` / `build_parser()`)

**LIVE `tw` verbs today** (re-verified 2026-08-10 against tip `build_parser()` choices):
`attach`, `chain`, `chains`, `coach`, `do`, `ensure`, `explore`, `frames`, `history`, `log`/`trail`,
`loops`, `menumap`, `mine`/`patterns`, `pairs`, `planet-colonization`, `players`, `port-floor`,
`probe`, `read`, `record`, `reflex`, `report`, `rule`, `screen`, `send`, `servers`, `skill`,
`status`, `stop`, `teach`, `watch`.

`pairs` (**WO-CHAIN-DETECT-WIRE**, re-scoped 2026-07-28) is the thin product caller over the
class-derived pair-loop path: `chain_detect.recompute` reads a world's `state/world/<world-id>`
port records and returns a typed `PairLoopResult` (a ranked tuple of margin-unknown `CandidatePair`
rows, or one of five typed empty reasons); `chain_detect_view.format_candidate_pair_lines` renders
it. Daemon-free like `loops` above — no `--run-dir`, `--world-id` required. Exit code is always
**0**: every typed empty reason is a successfully-established fact about the world, never a failed
read. Deliberately NOT the taught `L)chains` arm list (`cockpit/chains.py`) — a discovered,
unpriced pair rendered through that surface would be indistinguishable from a taught,
human-armed macro at the money-spending confirm gate.

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
pressed, is real future work X6's own scope explicitly excluded, not a change of target — tracked
as [`WO-AUDIT-BUILD-CLI-LIVE-ATTACH-RECORDER-X6`](../../workorders/WO-AUDIT-BUILD-CLI-LIVE-ATTACH-RECORDER-X6.md);
see [Macros](/engine/macros.md)'s Findings for the mirrored note.

**NOT a `tw` CLI verb on tip (HOLD / later / retired — do not document as runnable):**
`spectate` (**RETIRED / WONTBUILD** — Max; in-cockpit Spectate LIVE via PWO-055),
`start` (ensure covers spawn), `replay`,
`play`/`haggle`/`autopilot`/`crawl`/`autoloop` (shell), `aiclient` as a separate curses
product entry (product is `./tw2002-aiclient`). See the LIVE list above for the tip-true set
(`chain`, `coach`, `players`, `port-floor`, `planet-colonization`, `teach`/`skill`, `frames`, …).

**WIRE-ONLY (a daemon protocol verb exists; no `tw` CLI subparser wraps it — not runnable from a
shell today, only over the daemon's own socket protocol):**

- **`state`** (**X1**, `protocol.py` `verb == "state"`) — the parsed current-sector read replay's
  start-anchor guard depends on. `WO-P2-G4-X1-STATE-SECTOR-READ` scoped a CLI wrapper as optional
  ("+ thin CLI if honesty requires") and none landed.
- **`autoloop_start` / `autoloop_stop` / `autoloop_status` / `autoloop_pause` / `autoloop_relaunch`**
  (**X4/X5** + WO-AUTOLOOP-PAUSE-RESUME, `protocol.py`) — the background AUTO-LOOP player.
  **Not** the catalog's four-verb `{start,stop,pause,resume}` surface: five wire verbs
  shipped. `autoloop_pause` and `autoloop_relaunch` landed under the 2026-07-27 hub ruling
  (options 1+3): pause parks intent and hands the keyboard back; relaunch re-arms from macro
  step 1 (a fresh start that re-issues sends already made — **not** a thaw).
  **`autoloop_resume` stays `unknown_verb` deliberately** — a caller asking for continuation must
  not silently get a relaunch. Of the catalog row's key args, `name`, `floor`, `turn_budget`, and
  `cycles` are accepted (`autoloop.ARGS_AUTOLOOP_START`) because each is **enforced**: `floor` and
  `turn_budget` halt fail-closed when unobservable/exhausted; `cycles` is clamped to
  `CYCLES_HARD_CEILING` (never unbounded). `param` and `force` are **refused** as
  `unsupported_arg`, never silently ignored. No `tw autoloop` CLI subparser wraps these; the
  catalog row states the full future target, this paragraph states wire-level reality today.

The catalog tables **above** are the **prescriptive full vocabulary** (target). Prefer this status
block when answering "what can I run right now?"

# Code Divergence

1. **Catalog vs tip help (WO-ESCALATE-CLI-VERBS Option B).** Catalog rows for teach / App-drive /
   HOLD verbs are marked **TARGET** (or WIRE-ONLY / RETIRED) so they cannot be read as shipped
   `tw` subcommands. Tip `f14cc30` LIVE set is listed in Implementation status — honesty gate:
   never claim a HOLD or unported verb is runnable. (`frames` was catalog-LIVE + wired after
   #642 / `f3b2f33` but omitted from the enumerated LIVE list until
   `WO-CANON-FIX-CLI-VERBS-FRAMES-LIVE-LIST` — closed.)

2. **Citations historically pointed at `twclient/cli.py`.** Authoritative tip parser is
   `tw2002_aiclient/session/cli.py` (ADR-001 relocate). Archive paths remain port-source for verbs
   not yet restored.

3. **`tw autopilot` — TARGET / WONTBUILD as a reasoning driver (tension closed).** Under reborn
   canon the App is a **deterministic** autopilot that plays only taught, human-approved rules and
   **stops on any unknown screen** — it does not "reason" or run a per-cycle EV chooser. Tip has
   no `tw autopilot` verb and no live `autopilot.py` (archive-only / do-not-revive; see
   [App Autopilot Model](/architecture/app-autopilot-model.md)). Live playback is
   `loops/player.py` + wire `autoloop_*` — unattended-and-unguarded *by construction* only in the
   taught-step sense (no guard/arming field inventing keystrokes). Catalog row stays TARGET for a
   possible future shell wrapper around taught orchestration; it is **not** an open design tension
   about AI/EV live-drive.

4. **`record`'s catalog row now documents a shape that was deliberately shipped different from
   what this concept originally specified.** X6's manifest writer (see Implementation status
   above) replaced the originally-catalogued live `{start,stop}` bracket capture as the *first*
   step, not the final one — the lane disclosed the gap and the hub Accepted it as an honest,
   correctly-scoped increment; live-attach capture is deferred, real future work, not abandoned
   target. This is this concept's first instance of DOCS WIN running in reverse: a genuinely
   Accepted shipped-shape difference that canon must catch up to, rather than code drifting from a
   canon that stayed right. `autoloop`'s wire-vs-CLI split and its pause + relaunch-not-resume
   contract (Implementation status above; citations [5]/[6]) are the same class of finding —
   recorded there rather than repeated here.

# Citations

[1] `tw2002_aiclient/session/cli.py` — `build_parser()`, tip authoritative LIVE verb list
[1c] `tw2002_aiclient/frame_recorder.py` / `frames_cli.py` — `FrameRecorder` settle write-path + `tw frames {tail,show,grep,diff}` (WO-BUILD-CLI-VERBS-FRAMES)
[1b] `tw2002_aiclient/mine_cli.py` — `add_mine_parsers` / `cmd_mine` (`tw mine` / `tw patterns` wrapper)
[2] `canon/architecture/control-and-escalation.md` — actor model, approval gate, stop-on-unknown
[3] Archive `twclient/cli.py` — port-source for verbs not yet restored
[4] Project `CLAUDE.md` — hard rules / seat context
[5] `tw2002_aiclient/session/protocol.py` — `dispatch()`, the wire-verb chokepoint (`state`,
    `autoloop_start`/`_stop`/`_status`/`_pause`/`_relaunch`; `autoloop_resume` deliberately
    `unknown_verb`) and each verb's accepted/refused argument set
[6] `tw2002_aiclient/session/autoloop.py` — `ARGS_AUTOLOOP_START` (`name`/`floor`/`turn_budget`/
    `cycles`), `CYCLES_HARD_CEILING`, and refusal of `param`/`force` as `unsupported_arg`
[7] `tw2002_aiclient/loops/recorder.py` + `cmd_record` (`tw2002_aiclient/session/cli.py`) — the X6
    manifest-based recorder's real shape
