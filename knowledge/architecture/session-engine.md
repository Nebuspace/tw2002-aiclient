---
type: System
title: Session Engine — Daemon, Settle Detection, Classification, and Control Lock
description: The built two-process engine (a session daemon plus a one-shot CLI) that gives an LLM a clean, settled screen back in one round trip while a control-lock mode machine governs who may drive it.
tags: [session-engine, daemon, cli, settle-detection, classification, control-lock, built]
resource: repo://twclient
timestamp: 2026-07-19T16:12:01Z
---

The session engine is the built foundation everything else in the client stands on: a persistent
daemon that owns the one telnet connection to the game, and a stateless one-shot CLI that a
Bash-driving agent calls one verb at a time. This concept describes engine reality, verified
against the code as of this writing.

# Architecture — the daemon/CLI split

Two processes, one connection:

- **The session daemon** owns exactly one telnet socket to the game server, feeding the raw byte
  stream through telnet negotiation handling into a terminal emulator that maintains the current
  80x25 screen. It tracks the time since the last received byte for settle detection, and serves
  a JSON protocol over a local unix-domain socket.
- **The one-shot CLI** is stateless: it opens the socket, issues exactly one verb, prints the
  response, and exits. This is the interface an LLM-driving agent calls — a single round trip
  sends input and gets back the resulting settled screen, with no send-then-poll dance required
  on the caller's side.

The daemon refuses a second connection outright — this is deliberately a single-connection,
single-session engine, not a multiplexer.

# Settle Detection — the reliability core

After any send, a screen is considered **settled** on the first of three conditions to fire:

1. **prompt** — a caller-supplied regex matches the rendered screen.
2. **idle** — no new bytes have arrived for a debounce window (default 350ms), and at least one
   byte has arrived since the send (so a screen that was already idle before the send doesn't
   trivially "settle" against stale content).
3. **timeout** — a caller-supplied timeout elapses regardless.

The response reports which of the three fired (`settled_reason`), so a caller can tell a
confirmed prompt match from an idle guess from a hard timeout. A stricter positive-confirmation
variant exists for sends that must not be answered against an unverified screen: it requires a
freshly-rendered confirmation before treating a send as acknowledged, rather than settling on
idle alone — this is what makes an automated send safe to fire without risking it landing against
a stale or in-flight screen.

# Screen Classification

The rendered screen is classified via regex anchors run against the current text, producing one
label such as `login_name`, `login_password`, `pause_key`, `main_command`, `computer`,
`sector_display`, `port_trade`, `menu`, or `unknown`. Anchors are split into two kinds with
different matching rules:

- **Gate anchors** (the login prompts, the pause key, the main command prompt) represent a
  single currently-active blocking question and are only trusted against the *current* prompt
  line — a match sitting deeper in stale scrollback is leftover text, not a live gate, because
  the terminal emulator does not clear cells the server never overwrote.
- **Content anchors** (sector display, port trade, menu) describe what kind of screen is showing
  and are allowed to match anywhere in the full rendered text, since that content legitimately
  sits above the current prompt line rather than only on it.

Gate anchors are checked in a deliberate order so a more specific prompt (e.g. the in-game
computer subsystem's command line) wins over a more generic one it would otherwise also match
(the plain ship command line).

# Control Lock — who may drive

A mode state machine governs who is currently allowed to drive the one game connection:

| Mode | Meaning |
|---|---|
| `ai_pilot` (default) | The AI drives; ordinary driving verbs succeed. |
| `human` | An interactive attach session holds the keyboard exclusively; every driving verb from any other caller is rejected outright, never queued or interleaved onto the wire. Connection-scoped: entering and leaving this mode is tied to one connection's own lifetime, so a crashed or killed attach session can never leave the daemon wedged in it. |
| `spectate` | Driving is paused; nobody is driving. A read-only observer surface can watch this state without ever entering the state machine itself. |
| `auto_loop` | The daemon's own background learned-loop player is driving solo, with no external caller involved. Exclusive, but not tied to any client connection, since the player is a daemon-owned background thread rather than a caller's session. |

`human` and `auto_loop` are each exclusive and can only be entered or left through their own
dedicated pair of calls (never through a generic mode-set), so a vanished caller can never strand
the daemon in an exclusive mode it never properly released. `ai_pilot` and `spectate` are plain
standing toggles any driving verb can set, and setting one never clobbers an active `human` or
`auto_loop` hold out from under whatever currently owns it.

# Credential Handling

Login credentials are resolved with an environment-variable-first precedence over a local,
out-of-band secrets store, so a password never has to be written to disk to run a session (a
throwaway or CI profile can supply one purely via environment). When a password does need to
persist, it is written to a dedicated secrets file created with owner-only permissions and
re-asserted on every write. Every password send — whether typed by the login automaton or
resent verbatim during a retry — routes through one redaction path shared by the session
transcript logger, so a password is never written into a log or transcript in cleartext.

# Examples

```
$ tw start --profile main
{"settled_reason": "prompt", "classification": "login_name", "prompt": "What is your name?"}

$ tw do "AEGIS" --wait-prompt "password"
{"settled_reason": "prompt", "classification": "login_password", "prompt": "Password:"}
```

# Citations

[1] design history (v1) — the CLI/daemon split, the socket protocol, and the settle-detection design
[2] design history — telnet negotiation handling and terminal emulation
[3] design history — the control-lock mode machine and its exclusivity rules
[4] design history — the secure credential store and redaction path
