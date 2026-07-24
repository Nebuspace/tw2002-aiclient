---
type: System
title: Session Engine
description: The persistent daemon plus one-shot CLI that own the single telnet connection and terminal, serve the JSON verb protocol as the one contract, and carry every keystroke through the control-lock with an {app,human} send-time actor tag.
tags: [architecture, session-engine, daemon, cli, transport, control-lock]
timestamp: 2026-07-23T19:47:45Z
---

The session engine is the substrate every other concept stands on: a persistent daemon (`twd`)
that owns exactly one telnet connection to the game and the one terminal emulator that renders it,
and a stateless one-shot CLI (`tw`) that is what a driving worker actually calls — one verb, one
round trip, a settled screen back. It owns the transport (raw socket, telnet negotiation, terminal
emulation), the unix-socket JSON verb protocol that is the sole contract between the two processes,
and the choke point through which every keystroke passes on its way to the wire. It does **not**
decide *what* to send — that is the reflex layer ([the Rule–Macro Engine](/architecture/rule-macro-engine.md))
driven by the run-loop ([the APP Autopilot Model](/architecture/app-autopilot-model.md)) — nor
*who may* send it, whose mechanics belong to [Control & Escalation](/architecture/control-and-escalation.md).
This concept specifies the machinery those decisions ride on.

# The Two-Process Split

Two processes, one connection:

- **`twd`, the session daemon**, is persistent. It owns the single telnet socket, the pyte-emulated
  terminal, the settle-detection bookkeeping, and per-world continuity. It is spawned detached for
  the caller by `tw start` (or `tw ensure`); it is never invoked by hand.
- **`tw`, the one-shot CLI**, is stateless. Every verb is a single **connect → send one JSON
  request → read one JSON line → disconnect** round trip. The caller never holds a socket open,
  never runs a send-then-poll loop: it issues one verb and gets back the resulting *settled* screen
  in the response. This is the shape a Bash-driving worker composes against — one round trip per
  action. The full verb vocabulary is cataloged in [the CLI Verb Surface](/architecture/cli-verbs.md);
  the mechanics of a round trip are owned here.

The split is deliberate: continuity lives in the daemon, so the thing that *decides* keystrokes can
be disposable (see [Rolling-Pilot Operating Model](#rolling-pilot-operating-model) below).

# One Package Tree

*— per [ADR-001](/ADR/001-one-tree-embedded-session.md) (Proposed; Max ruling 2026-07-23), pending Accept*

The two-process split above is a **process** boundary, not a **package** boundary: it does not
imply, and must not be built as, two top-level importable packages. There is exactly one top-level
importable package, `tw2002_aiclient/`. The daemon (`twd`), the one-shot CLI (`tw`), transport, and
credentials — everything currently cataloged in this project's `CLAUDE.md` Architecture map under
the sibling `twclient/` package — live under `tw2002_aiclient/session/`; the product TUI app and its
screens live under `tw2002_aiclient/` directly. Console scripts `tw` and `twd` point **into**
`tw2002_aiclient.session.*`, never into a second top-level package. Embedding both processes' source
into one import tree does not collapse them to one process — `twd` and `tw` (and the TUI app) remain
separate OS processes exactly as "The Two-Process Split" above specifies; this section is packaging
shape only.

The current on-disk scaffold (from WO-P0-003) still stands up `tw2002_aiclient/` and `twclient/` as
two sibling top-level packages — a Phase-0 gap Max caught in review, not the target state. Relocating
`twclient/*` into `tw2002_aiclient/session/*` and repointing every import path and console-script
entry is deferred to a follow-on work order, gated on ADR-001 moving to Accepted (see ADR-001's
Consequences for the itemized follow-on list, including the WO-P0/P1/P2 Proof-path updates and this
document's own module Citations below, which are **not** rewritten by this section — they still
correctly describe the current `twclient/*` layout until the relocate lands).

**App-owned daemon lifecycle.** The aiclient app — the process the player actually runs — may
start/ensure the daemon on entry (via `tw ensure`-equivalent machinery), so the player never has to
invoke `twd` by hand. On the player's **exit** from the aiclient app, a confirm popup asks whether to
stop the daemon along with the client — **"Stop the daemon too? (Yes / No)"** — rather than silently
leaving a live game session either orphaned in the background or force-killed out from under a
reattachable session. The popup itself is a surface concern; it is specified in
[the Trainer Cockpit](/surfaces/trainer-cockpit.md)'s "Exit flow" section, which this section
cross-links as the UX home for the decision this lifecycle rule makes possible.

# Single-Connection Invariant

This is a single-connection, single-session engine, not a multiplexer. The daemon writes a
**pidfile** and a **unix socket** into a project-rooted `run/` directory (`run/twd.pid`,
`run/twd.sock`) regardless of the caller's working directory. On startup `twd` reads the pidfile;
if a live process still holds it, the second daemon **refuses to start** rather than opening a
competing connection to the game. A stale pidfile (no such process) is stepped over. This is a hard
invariant — there is never more than one telnet connection to a given game from this engine.

# The Unix-Socket JSON Verb Protocol

The one contract between `tw` and `twd` is a newline-delimited JSON protocol over the local
unix-domain socket. Each request is `{"verb": <name>, "args": {...}}`; each response is one JSON
line. Two verbs are lifetime exceptions to the one-shot shape — their connection *is* their
lifetime rather than a single request/response: `subscribe` (the settle-edge push stream behind
`tw watch`/`tw spectate`) and `attach` (an interactive `tw attach` session's whole control-lock
hold; every subsequent line is one raw keystroke frame). A malformed request line is answered with
a structured error and **never crashes the daemon** — a bad request must not take the connection
down. The response the driving verbs return is assembled at one choke point that renders the
current screen, classifies it, parses best-effort state, and stamps the `settled_reason`; the
detection of *settled* itself is owned by [Settle Detection](/architecture/settle-detection.md) and
consumed here.

# The Transport It Owns

The daemon owns the whole path from wire bytes to a rendered screen:

- **Raw socket + a background reader thread.** One `recv()` loop pulls bytes off the telnet socket
  on its own thread and feeds them forward under a lock. Anything reading the screen from another
  thread (a command-socket handler building a response) takes the same lock.
- **A hand-rolled telnet IAC state machine.** Python 3.13 removed `telnetlib`, so IAC (Interpret As
  Command) negotiation is a small persistent byte-level state machine: it **strips IAC command and
  subnegotiation sequences out of the inbound stream before pyte ever sees them**, and answers the
  option negotiation (WILL/WONT/DO/DONT) and the TTYPE/NAWS subnegotiations a TWGS door expects.
  The state persists across `recv()` calls, so a sequence split across two reads is handled
  correctly. Only IAC-clean data reaches the emulator.
- **An 80×25 pyte terminal under lock.** Clean bytes feed a pyte `Screen`. TWGS is a DOS BBS door:
  its box-drawing/line-art bytes are **CP437, not UTF-8**, and are decoded as CP437 (single-byte,
  safe to decode per chunk) so the game art renders as glyphs rather than mojibake.
- **A token-efficient, content-cropped render.** The default screen handed back is cropped to its
  content bounding box — trailing blank rows and columns trimmed, leading layout preserved — so a
  driving worker spends tokens on live content, not on 80×25 of trailing whitespace. A raw,
  uncropped grid and a run-length-encoded color map are available for the surfaces that need them
  (`tw screen --raw`, the spectator's color view).

# The Control-Lock as Keystroke Carrier

Every keystroke bound for the game passes through the daemon's send choke point, and the
**control-lock** governs whether it is allowed onto the wire. The lock is a mode state machine —
the *policy* of who may drive (App / Human / Spectate, and the background AUTO-LOOP holder) is
specified in full by [Control & Escalation](/architecture/control-and-escalation.md); this concept
owns the *carrier* mechanics the lock rides on.

**Exclusive active-driver guard (TW-04).** Because the CLI is one-shot, there is no persistent
connection to hold a lock across, so two `tw do` calls racing in from separate connections could
otherwise interleave two logical conversations onto the one wire. The lock reserves a single
**active-driver slot** for the whole duration of one send-then-settle dispatch: a second concurrent
driver is **refused outright, never queued** (queuing would mean holding a stranger's one-shot
socket open indefinitely). Mode and slot are claimed under one atomic lock hold, so nothing can
slip a mode change between the check and the claim. A refusal surfaces as a `ControlModeConflict`
naming *why* (`controller_locked_by_human` / `controller_locked_by_auto_loop` / `controller_busy`).
A human `tw attach` always wins the keyboard **instantly** even over an in-flight dispatch: the
dispatch is *fenced* rather than refused, and the human's first keystroke is held off the wire only
until that fenced dispatch releases — a clean cutover onto the one wire, never a silent two-writer
interleave.

**Send-time actor tag `{app, human}` + `session_id`.** At the moment a keystroke reaches the wire,
the engine tags it with the actor that originated it — **`app`** or **`human`**, the only two live
senders in the reborn model (the AI is a retrospective author, never a live sender; see
[Control & Escalation](/architecture/control-and-escalation.md)) — plus the daemon's continuous
`session_id`. This is the *attribution substrate* that control-and-escalation defers to the session
engine: the tag is applied here, at the carrier; the **full ledger-row schema** (what fields a
recorded action carries, how they are stored and read back) is owned by
[the Trace Ledger](/engine/trace-ledger.md). The `session_id` is the daemon's own
per-run id, reused as-is so a ledger row and its transcript file correlate for free.

**Redaction invariant at the protocol boundary.** Secrets never touch logs, argv, shell history, or
the repo. Every password-bearing send routes through the one redaction path (`log_redacted()`): the
send choke point decides `secret` from the *current* screen right before the byte hits the wire,
and that single decision gates all three sinks — the transcript log (redacted line instead of the
bytes), the ledger row, and the `sent_input` field a status/spectator read exposes — so no sink can
disagree or leak. Interactive `tw attach` keystrokes re-derive `secret` fresh per keystroke from
the live prompt, never from a stale pre-wait screen. This concept states the invariant *at the
boundary*; the full credential-handling discipline lives in
[Secrets & Credentials](/doctrine/secrets-and-credentials.md).

# Rolling-Pilot Operating Model

The daemon is **continuity**; the driving worker is **disposable** (J3). Because `twd` owns the
connection, the terminal, and per-world state, the process that decides keystrokes — a Bash-driving
LLM worker, the App autopilot loop, or a human at `tw attach` — can be swapped, restarted, or lost
without dropping the game session. A fresh worker attaches by issuing its next one-shot verb against
the still-live daemon and gets the current settled screen back, exactly as if it had been there all
along. This is why the two-process split exists rather than a single long-lived client: the
sovereign line (App/Human dual, escalate-on-unknown) stays intact across worker churn.

# Config Bootstrap

`tw start` resolves the game host/port through `env.py`, a pure-stdlib `.env` loader with a fixed
precedence — explicit CLI arg → process environment (`TW2002_HOST`/`TW2002_PORT`) → repo-root
`.env` → `config/profiles.toml` `[default]` → a hard error naming the missing variable (no silent
fallback host). This mirrors the env-first idiom credential resolution already uses.

# Schema

| Surface | What the engine owns | Where the boundary is |
|---|---|---|
| Two-process split | Persistent `twd` (connection + terminal + continuity); stateless `tw` one-shot verbs | Verb catalog → [CLI Verb Surface](/architecture/cli-verbs.md) |
| One package tree *(ADR-001, Proposed)* | Single top-level `tw2002_aiclient`; daemon-core lives under `tw2002_aiclient/session/`; console scripts point into it | Exit-popup UX → [Trainer Cockpit](/surfaces/trainer-cockpit.md) |
| Single-connection | Project-rooted `run/twd.pid` + `run/twd.sock`; pidfile refuses a 2nd daemon | — (hard invariant) |
| JSON verb protocol | `{verb,args}` → one JSON line; `subscribe`/`attach` are lifetime-connections; bad request never crashes daemon | Settled-ness → [Settle Detection](/architecture/settle-detection.md) |
| Transport | Raw socket + reader thread; hand-rolled IAC (stripped before pyte); CP437 80×25 pyte under lock; content-cropped render | — |
| Control-lock carrier | Exclusive active-driver slot (refuse-not-queue); instant human preemption via fencing; send-time `{app,human}`+`session_id` tag; boundary redaction | Drive policy → [Control & Escalation](/architecture/control-and-escalation.md); ledger schema → [Trace Ledger](/engine/trace-ledger.md) |
| Rolling-pilot | Daemon = continuity; driving worker = disposable | — |
| Config bootstrap | `env.py` host/port precedence chain | — |

# Examples

One `tw do` round trip — connect, send one verb, read the settled screen, disconnect:

```
$ tw do "1" --wait-prompt "Command \[TL="
<the settled screen rows>
--- prompt: Command [TL=00:14:22]:12345 | class: main_command | settled: prompt
```

A disposable worker reattaching to a still-live daemon — no reconnect, no state handoff:

```
$ tw status            # a fresh shell, the previous worker gone
daemon_running: true · connected: true · class: port_trade
$ tw screen            # the current settled screen comes straight back
```

A redacted send at the protocol boundary — the password never reaches any sink in cleartext:

```
$ tw do "hunter2" --secret --wait-prompt "Command \["
--- class: main_command | settled: prompt
# transcript log line: TX <redacted> ; ledger actor+input: <redacted> ; status sent_input: <redacted>
```

# Code Divergence

**(1) Send-time actor tag emits `ai`/`trainer`, not `app`.** The reborn model has exactly two live
senders, `{app, human}`. The code's ledger attribution currently tags App-originated sends with a
richer, older vocabulary: `do`/`send` dispatch hardcode `actor="ai"`, `haggle` and the background
AUTO-LOOP driver (`loop_player.py`) tag `actor="trainer"`, and `_current_actor()` returns `"ai"` in
the default mode. Human keystrokes are already tagged `actor="human"` (attach). Under this canon
every App-executed keystroke — autopilot, learned-loop playback, auto-haggle alike — is a single
`app` sender; `ai` and `trainer` collapse into `app`. Documentation-only finding; the tag rename is
a future work order and the full row schema is [the Trace Ledger](/engine/trace-ledger.md)'s to
carry.

**(2) `MODE_AI_PILOT` as a live-drive mode.** The control-lock still defines an `ai_pilot` mode in
which "the AI drives." That contradicts the reborn control model. This divergence is **already
recorded** by [Control & Escalation](/architecture/control-and-escalation.md)'s Code Divergence
section — it is not restated here; the carrier mechanics above describe the `{app, human}` target
state.

# Citations

[1] internal design history (v1) — the CLI/daemon split, the unix-socket JSON protocol, and the
one-round-trip settle-return shape
[2] internal design history (v2) — the transparency TX channel and the send-time attribution/
`session_id` substrate (TW-05)
[3] twclient/daemon.py, cli.py — the two-process split, pidfile single-connection guard, and the
subscribe/attach lifetime-connections
[4] twclient/connection.py, iac.py, terminal.py — background reader thread, hand-rolled IAC
stripping, CP437 80×25 pyte render
[5] twclient/control_lock.py — the active-driver slot, human-preemption fencing, and mode machine
[6] twclient/session.py, protocol.py — the send choke point, boundary redaction across all three
sinks, and the `{actor, session_id}` ledger tag
[7] twclient/env.py — the host/port resolution precedence chain
