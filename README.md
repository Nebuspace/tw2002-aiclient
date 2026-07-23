# tw2002-aiclient

> **Teach an AI to fly a starship from 1991 — then watch it get good.**

[TradeWars 2002](https://en.wikipedia.org/wiki/TradeWars_2002) is the cult-classic
BBS space-trading game: a raw telnet stream of ANSI art, cryptic menus, and
haggling port merchants. It was never meant to be played by a machine.

**tw2002-aiclient makes it playable by one.** A persistent daemon owns the telnet
connection and a real terminal emulator; an LLM plays the game through a one-shot
CLI — one command per turn, a settled screen back, ready to parse. And while the
AI grinds trade routes in the background, *you* get the fun parts: a live color
dashboard to watch it fly, a keyboard to take over any time, and a client that
quietly learns the profitable loops it sees.

### Product vs ops

| Surface | Role |
|---|---|
| `./tw2002-aiclient` | **Product TUI** — profile launcher, play screen, Autopilot ON/OFF. Human-facing client. |
| `./tw` | **Backend / ops CLI** — daemon verbs (`ensure`, `do`, `status`, …), scripting, and ops surfaces. |
| `./tw spectate` | **Ops spectator** — read-only live HUD for operators/scripts (`tw aiclient` is the product path). |
| `./tw attach` | Take the keyboard on the shared session (also reachable from ops workflows). |

Same daemon either way — one telnet connection. Prefer `./tw2002-aiclient` for day-to-day play; keep `./tw` for automation and ops.

---

## What it does

**🤖 An AI can actually play.** The core problem with driving a telnet game from
an agent is that the stream never says "your turn." This client solves it with a
settle-detection engine: `tw do "T"` sends a keystroke, waits until the screen has
genuinely stopped changing, and returns the new screen plus a classification of
the prompt it landed on — one command, one clean round trip. No timing guesswork,
no half-drawn screens.

**📺 Watch it play, live and in color.** `tw spectate` opens a curses dashboard
in your own terminal: the game screen in its real ANSI colors, a parsed-state
sidebar (credits, sector, turns), an event ticker, and a live readout of every
keystroke the AI sends. It's a pure observer — run it any time, from any
terminal, with zero coordination with whoever is driving. Any number of
spectators can attach at once.

**🕹️ Take the wheel whenever you want.** `tw attach` drops you into the live
session as the player — full-screen, real color, your keystrokes going straight
to the game. No re-login, no restart; you inherit the session mid-flight. Press
`Ctrl-]` and control hands cleanly back to the AI. A control lock guarantees
exactly one driver at a time: while you hold the keyboard, the AI's commands are
rejected outright, and taking over fences any AI command already in flight so
control passes cleanly.

**🔐 It logs itself in.** `tw ensure` is the one command for getting into the
game: it spawns the daemon if needed, then drives registration or login all the
way to the command prompt — picking the game, dismissing interstitials, even
registering a brand-new character and generating its password. Credentials live
in a chmod-600 local store (or an env var) and are redacted everywhere: your
password never appears in logs, argv, shell history, or any output. If the
connection drops, a background guardian reconnects and logs back in by itself.

**📈 It learns.** As the AI plays, the client records what works: a trace ledger,
a macro record/replay engine, and a profit-miner that proposes profitable trade
loops from what it has seen. Learned loops are browsable from the dashboard's
built-in library (or `tw loops`), and `tw autoloop` hands one to a background
player that flies it solo — pause, resume, or panic-stop from the spectator's
control strip. The north star is an old-fashioned trainer: the AI teaches, the
client is the trainee that graduates to solo flight.

**🧪 Built to be reliable.** Settle detection is the reliability core, and the
whole stack — telnet negotiation, terminal emulation, classification, login
automaton, control lock, learning engine — is covered by a large, fully
network-free test suite driven by fake clocks and scripted sessions.

---

## How it fits together

One long-lived daemon, many short-lived windows into it:

```
  AI agent ──── tw do / screen / state ────┐
  (one-shot CLI verbs, one round trip)     │
                                           ▼
  you ──── tw spectate (watch) ────▶ ┌──────────────┐
                                     │ twd (daemon) │ ── telnet ──▶ TW2002 server
  you ──── tw attach (play) ───────▶ │  the ONE     │
                                     │  connection  │
  autoloop player (learned loops) ──▶└──────────────┘
```

- **The daemon (`twd`)** owns the single telnet connection and a pyte terminal
  emulator, watches for "settle edges" (the screen stopped changing and is new),
  and serves everything over a local unix socket. You never run it directly.
- **The CLI (`tw`)** is stateless: every verb connects, asks, prints, exits.
  That's what makes it drivable from an agent's shell, a script, or your hands.
- **`spectate` and `attach`** are the human surfaces layered on the same daemon —
  watch or drive, without disturbing the session.
- **A control lock** arbitrates the one connection: AI pilot, human at the
  keyboard, autoloop player, or nobody — exactly one driver at a time, always.

Deep architecture and rationale: see [`DESIGN.md`](DESIGN.md) and
[`CLAUDE.md`](CLAUDE.md); canonical docs are being established in `knowledge/`.
Day-to-day product + ops path (launcher → Autopilot → attach, run-dir isolation,
`--no-auto-arm` recycle, live seat recovery): [`docs/OPERATOR.md`](docs/OPERATOR.md).

---

## Quickstart

```bash
git clone <this repo> && cd tw2002-aiclient
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # one dependency: pyte
```

`./tw2002-aiclient` and `./tw` are self-locating — they run from anywhere by
absolute path, no venv activation needed.

**Product path** (launcher → create/select profile → play / Autopilot):

```bash
./tw2002-aiclient --help    # title: tw2002-aiclient; points at ./tw for ops
./tw2002-aiclient           # curses product TUI (needs a real TTY)
```

**Ops / backend path** — get into the game (handles daemon spawn, login/registration,
credential storage):

```bash
cp config/profiles.toml.example config/profiles.toml   # once; set host/game/handle
./tw ensure --profile default
```

**Play a turn, look around:**

```bash
./tw do "D" --wait-prompt "Command"    # send a key, get the settled screen back
./tw screen --json                     # look without acting
./tw state --json                      # just the parsed fields: sector, credits, turns…
```

**Watch and join in, from any other terminal:**

```bash
./tw spectate     # live color dashboard — q to leave
./tw attach       # take the keyboard — Ctrl-] to hand back
```

**Wind down cleanly:**

```bash
./tw stop         # in-game QUIT, disconnect, daemon exit
```

## Verb reference

Everything takes `--json` for machine-parseable output.

| Verb | What it does |
|---|---|
| `tw ensure [target] --profile NAME` | **Auto-login.** Idempotent: spawn daemon if needed, register or log in, land at the command prompt. Covers cold start, mid-session, and post-drop recovery. |
| `tw do "<input>" [--wait-prompt REGEX]` | **The primary verb.** Send input, wait for the screen to settle, return the new screen + why it settled. |
| `tw screen` | Current settled screen, prompt, classification — non-destructive. |
| `tw state` | Parsed game state only (sector, credits, turns, port…), best-effort. |
| `tw status` | Daemon alive? Connected? Who's driving? Always safe to run. |
| `tw start [--host H --port P]` | Manual daemon spawn + connect (use `ensure` unless you need low-level control). |
| `tw read [--wait-prompt REGEX]` | Wait-and-return without sending — for unsolicited server output. |
| `tw send "<input>"` | Raw send, no wait (low-level). |
| `tw history [--n N]` | Recent events; full transcript in `logs/`. |
| `tw watch [--frames N]` | Tail the settle-edge event stream — the scripting-friendly sibling of `spectate`. |
| `tw aiclient` | Product TUI alias for `./tw2002-aiclient` (launcher / play / Autopilot). |
| `tw spectate` | Ops read-only curses dashboard (`--snapshot` for scripting). |
| `tw attach` | Interactive live console — play the game yourself; `Ctrl-]` detaches. |
| `tw loops [--include-drafts]` | List every learned loop with profit metadata. |
| `tw autoloop {start,stop,pause,resume}` | Drive the background learned-loop player; returns immediately — watch progress in `spectate`. |
| `tw stop` | Clean in-game quit, disconnect, daemon exit. |

Notes worth knowing up front:

- `--wait-prompt` regexes are **case-sensitive** — a case mismatch times out
  silently rather than erroring.
- The daemon is single-connection, single-session; its socket and pidfile live
  under the project directory regardless of where you invoke `tw` from.
- Plain CLI output is deliberately color-stripped (token-efficient for agents);
  `tw spectate` is where the real ANSI colors live.

## The spectator's control strip

Inside `tw spectate`, a compact control strip lets you direct the client without
leaving the dashboard:

| Key | Action |
|---|---|
| `M` | Cycle mode: AI-PILOT ↔ SPECTATE |
| `L` | Open the Learned-Loops Library — pick a loop, set cycles, `Enter` to launch |
| `Space` | Pause/resume the running auto-loop |
| `X` | Stop the auto-loop, return to AI-PILOT |
| `P` | Panic — halt everything, park in SPECTATE |
| `q` / `Ctrl-C` | Detach (the game keeps running) |

These are control-plane actions only — nothing in `spectate` ever forwards a
keystroke to the game. `tw attach` remains the only way to drive directly.

## Tests

```bash
.venv/bin/python -m pytest tests/
```

The suite is entirely network-free: telnet negotiation (including commands split
across packet boundaries), terminal rendering, prompt classification against
real captured fixtures, settle timing on a fake clock, the login automaton's
registration and recovery branches, the control lock's one-driver guarantees,
and the spectator/attach UIs against scripted sessions.

## Known limitations

- `state` parsing is a best-effort skeleton — extend the anchors in
  `twclient/state_parser.py` as new screen shapes turn up.
- `tw stop` only attempts the in-game QUIT from the main command prompt;
  elsewhere it just disconnects.

## Going deeper

- [`DESIGN.md`](DESIGN.md) — original architecture spec (CLI/daemon split,
  socket protocol, settle detection) and its rationale.
- [`CLAUDE.md`](CLAUDE.md) — module map and project conventions.
- `knowledge/` — living canonical documentation, being established.
