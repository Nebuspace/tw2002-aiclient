# tw2002-aiclient — an AI-native TradeWars 2002 client

**Author of record:** Samantha (Orchestrator). **Sole consumer:** an LLM agent (Claude), driving via subagent workers over Bash. **Not for human play.**

---

## 1. Purpose & the three things that make it "AI-native"

A client for the TradeWars 2002 TWGS telnet door whose entire design optimizes for an LLM in the loop:

1. **See a clean, *settled* screen.** Never a half-drawn frame, never raw ANSI noise — a cropped, emulated terminal grid plus a structured parse.
2. **Act in ONE round-trip.** A single verb sends input and returns the *resulting* settled screen. No send-then-poll dance for the agent.
3. **Stateful session across stateless calls.** A persistent daemon holds the telnet connection + terminal state; each CLI call is a thin, one-shot client. A Bash-driving worker never has to hold a socket open.

## 2. Decision — CLI + persistent session daemon (NOT an MCP, yet)

**Chosen: a CLI (`tw`) backed by a long-running session daemon (`twd`).**

Why not an MCP *now*:
- An MCP server must be registered and the Claude Code session reconnected to expose its tools. That needs a **session restart** — which would tear down the live merge coordination (coord-monitor, heartbeat) and context. The requirement is *build AND play this session*, so an MCP is disqualified for v1 on that constraint alone.
- Subagent workers "doing the playing" reach a **Bash** CLI natively; a freshly-built unregistered MCP is invisible to them this session too.

**MCP-ready by construction:** all game I/O lives in the daemon behind a small JSON socket protocol. A future MCP shim is a ~100-line translator (`tw_screen`/`tw_do`/`tw_state` → the same socket verbs). We lose nothing by starting CLI-first.

## 3. Architecture

```
 twd  (daemon, one per session)            tw  (CLI, one-shot, what workers call)
 ─────────────────────────────            ────────────────────────────────────────
 socket  ── IAC handler ── pyte Screen     connect ./run/twd.sock → 1 verb → print → exit
   │                          │
   └── settle-tracker (last-byte clock)     verbs: start screen do send read state
   listens on ./run/twd.sock  (JSON)               history status stop
```

- **`twd` session daemon:** owns ONE telnet socket to the server; feeds the byte stream through IAC handling into a **pyte** 80×25 terminal emulator; tracks the time of the last received byte (for settle detection); serves a JSON protocol over a unix-domain socket at `./run/twd.sock`.
- **`tw` CLI:** stateless; opens the socket, issues one verb, prints the response, exits. This is the agent/worker interface.

## 4. The AI-native verbs

| Verb | What it does |
|---|---|
| `tw start [--host <TW2002_HOST> --port 23 --name <handle>]` | Spawn daemon, connect, negotiate, return the first **settled** screen. |
| `tw screen [--json] [--compact] [--raw]` | **Non-destructive.** Current rendered screen (cropped), cursor, prompt-line, classification, parsed state. |
| `tw do "<input>" [--enter] [--wait-prompt REGEX] [--timeout 8] [--json]` | **THE primary verb.** Send input → wait until settled → return new settled screen + classification + state + `settled_reason`. |
| `tw send "<input>" [--enter]` | Raw send, no wait (rare / low-level). |
| `tw read [--wait-prompt REGEX] [--timeout] [--json]` | Wait-and-return WITHOUT sending (unsolicited server output). |
| `tw state [--json]` | Parsed structured game-state only. |
| `tw history [--n N]` | Recent screens/commands; full transcript at `./logs/session-<ts>.log`. |
| `tw status` | Daemon alive? connected? idle-ms? current classification. |
| `tw stop` | Graceful game QUIT → disconnect → daemon exit. |

Workers pass `--json` for machine-parseable output; humans/debug read the plain grid.

## 5. Screen representation (token-efficient)

- **Default view:** the pyte-rendered grid, **ANSI stripped**, cropped to the content bounding box (trailing blank rows/cols removed) — minimizes tokens per read.
- **`prompt`:** the last meaningful line — what the game is asking right now.
- **`classification`:** one of `{login_name, login_password, pause_key, main_command, sector_display, port_trade, computer, menu, unknown}` via regex anchors on the rendered screen.
- **`state`** (best-effort JSON, skeleton parsers extended as live play reveals screens): `{sector, turns_left, credits, warps:[...], port:{class, commodities:[{name,status,pct}...]}, ...}`.
- **Color:** stripped by default; `--raw` returns raw bytes for debugging; an optional per-cell color map is a phase-2 flag (TW2002 encodes danger/state in color).

## 6. Settle detection — the reliability core

After any send, the screen is **settled** when the FIRST of:
- **(a) prompt:** `--wait-prompt REGEX` matches the rendered screen, OR
- **(b) idle:** no new bytes for `debounce_ms` (default **350ms**), OR
- **(c) timeout:** `--timeout` seconds elapsed.

The response carries `settled_reason ∈ {prompt, idle, timeout}`. When a prompt regex was requested, we never return a half-drawn frame under it. This is what makes automated play deterministic instead of flaky.

## 7. Telnet / IAC

Raw `socket` (Python's `telnetlib` was removed in 3.13 — we own ~100 lines instead). Handle IAC negotiation: reply `DONT/WONT` to unsupported options; `DO TTYPE` → send terminal type `ANSI`; `DO NAWS` → advertise 80×25; handle `SGA`, `ECHO`, `BINARY`. **Strip IAC sequences from the data stream before feeding pyte.**

## 8. Guardrails (baked in — well-behaved single client)

- **Single connection:** the daemon refuses a second `connect`.
- **No hammering:** minimum inter-send delay (default **150ms**); polite, human-plausible pacing.
- **Graceful exit:** `tw stop` sends the game's QUIT path, then disconnects.
- **No secrets in the tree:** host/port/name via flags/env/`.gitignored` local config. No passwords committed.
- **Standalone:** lives at `Nebuspace/tw2002-aiclient/`, its own venv, its own git repo — independent of the Sectorwars2102/sw2102-bang/sw2102-docs siblings.

## 9. Stack

Python 3.x + venv. Dependencies: **pyte** (terminal emulator) — essentially the only third-party dep; everything else is stdlib (`socket`, `asyncio` or a reader thread, `json`, `argparse`). Possibly `wcwidth`. No heavy deps.

## 10. Tests (network-free)

- IAC stripping over canned byte streams.
- pyte render + crop correctness (fed a captured frame).
- Prompt classifier against captured TW2002 screen fixtures.
- Settle-detection timing with a fake clock.

## 11. Build phases (for Monk)

1. **Core:** IAC/telnet + pyte session + render/crop + daemon socket + CLI verbs (`start/screen/do/send/read/status/stop`) + transcript logging. **Get it connecting and settling.**
2. **Parsers:** classification + sector/port/prompt state extraction.
3. **Polish:** `--json` everywhere, `history`, reconnect-on-drop, color-map flag.

*(MCP shim is a future item, explicitly out of scope for v1.)*

## 12. Definition of done (v1)

- `tw start` connects to `<TW2002_HOST>:23`, negotiates, and returns the settled opening screen.
- `tw do "<key>" --wait-prompt ...` reliably returns the next settled screen with correct `settled_reason`.
- From a Bash subagent, the agent can see the login screen and drive to the game's main command prompt.
- Network-free tests pass. `README.md` + this `DESIGN.md` present.
