# tw2002-aiclient

An AI-native TradeWars 2002 telnet client. See `DESIGN.md` for the original v1
architecture spec and rationale; the living canonical documentation is being
established in `knowledge/`. This is the quickstart.

## Setup

```bash
cd tw2002-aiclient
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`./tw` and `./twd` are self-locating launcher scripts — an `sh` trampoline
execs this project's `.venv` python, so they run from anywhere by absolute
path, no `source .venv/bin/activate` needed.

## Verbs

| Verb | What it does |
|---|---|
| `tw start [--host H --port P --name NAME] [--timeout S]` | Spawn the daemon, connect, negotiate, return the first settled screen. |
| `tw screen [--json] [--compact] [--raw]` | Non-destructive: current settled screen, prompt, classification, state. |
| `tw do "<input>" [--enter/--no-enter] [--wait-prompt REGEX] [--timeout S] [--json]` | **The primary verb.** Send input, wait until settled, return the new screen + `settled_reason`. |
| `tw send "<input>" [--enter/--no-enter]` | Raw send, no wait (rare/low-level). |
| `tw read [--wait-prompt REGEX] [--timeout S] [--json]` | Wait-and-return without sending — for unsolicited server output. |
| `tw state [--json]` | Parsed structured game-state only (best-effort). |
| `tw history [--n N]` | Recent `do`/`read` events; full transcript at `logs/session-<ts>.log`. |
| `tw status [--json]` | Daemon alive? connected? idle-ms? current classification. |
| `tw stop` | Best-effort in-game QUIT, disconnect, daemon exit. |
| `tw ensure [target] --profile NAME [--timeout S]` | **Auto-login (v2 B1-B4).** The ONE command for login: idempotent — no-ops if already at `target` (default `main_command`), else drives registration-or-login all the way there using the profile's stored/generated credential, spawning the daemon first if none is running. No keystroke-by-keystroke driving and no remembering secrets — see "Auto-login" below. |
| `tw watch [--frames N] [--json]` | Tail the settle-edge push-stream — read-only, prints a new event every time the screen changes and settles. `--frames N` exits after N events (default: until Ctrl-C). |
| `tw spectate` | **Standalone, decoupled spectator.** Run in your own terminal, any time after `tw start` — attaches to the already-running daemon and renders a live curses dashboard (**real ANSI-colored screen** + parsed-state sidebar + event ticker + status line) of whatever is being played, by anyone, with zero coordination needed. `--snapshot [--frames N]` is a proof/scripting variant: prints plain-text dashboard frame(s) to stdout instead of the interactive loop (no color — curses only). |
| `tw attach` | **The driving seat.** Interactive live console: take the keyboard and play as the player yourself, full-screen and in real color, over the daemon's single game connection — you attach to the already-logged-in session, no re-authenticating. `Ctrl-]` hands control back to the AI. Rejected up front (before curses starts) if another human session is already attached. See "Taking the wheel" below. |
| `tw loops [--include-drafts] [--json]` | List every learned loop (recorded + optionally miner-drafted skills) with profit metadata — the CLI-scriptable twin of `tw spectate`'s in-TUI Learned-Loops Library (`L`). |
| `tw autoloop {start,stop,pause,resume} [name] [--cycles N] [--floor F]` | Start/stop/pause/resume the daemon's background AUTO-LOOP driver. Unlike `tw play` (blocks until the whole run completes), `start` returns immediately — watch it live with `tw spectate`'s control strip or `tw watch`. See "The Trainer Control Panel" below. |

Pass `--json` for machine-parseable output; the default prints the cropped
grid plus a one-line `prompt / class / settled` footer.

## How the AI plays with it

1. `tw start --host <TW2002_HOST> --port 23` — connects and prints the settled opening screen.
2. `tw do "<key or text>" --wait-prompt "<regex for the next expected prompt>"` — the one-round-trip primary action; check `settled_reason` and `classification` in the response.
3. `tw screen --json` any time you just need to look without acting.
4. `tw state --json` when you only want the parsed fields (sector, credits, turns_left, ...), not the raw grid.
5. `tw stop` when done — always disconnect cleanly rather than letting the server time you out.

The daemon is single-connection and single-session: `run/twd.sock` +
`run/twd.pid` live under this project directory regardless of your shell's
CWD when you invoke `tw`.

## Auto-login — `tw ensure` (v2 B1-B4, D9/D10)

**The client handles registration, password storage, login, and server
selection itself — an LLM never drives it keystroke-by-keystroke, and
never sees or remembers a password.**

```bash
cp config/profiles.toml.example config/profiles.toml   # once, then edit
.venv/bin/python3 -m twclient.cli ensure main_command --profile default
# or: ./tw ensure main_command --profile default
```

- **Credential store (B2):** `config/profiles.toml` (gitignored) holds
  non-secret shape — host/port/game_letter/handle — per profile. The
  password itself lives ONLY in `config/secrets.json` (gitignored,
  chmod 600, auto-created) or an env var `TW2002_PASSWORD_<PROFILE>`
  (checked first). A password never appears in the repo, `logs/*.log`,
  history, argv, or any response — sends go through the same
  `--secret`-style redaction path used elsewhere (`log_redacted`).
- **Login automaton (B1/B3):** a classification-driven expect/respond
  engine drives the real TWGS/TW2002 flow order-independently — name
  prompt, ANSI-graphics prompt, door-select menu (auto-picks the
  configured game letter), module-entry menu, then branches: RETURNING
  (saved password straight through to `Command [TL=…]`) or NEW-player
  registration (generates an 8-char password, **saves it immediately**
  — before the confirm round — then answers ship/planet naming through
  to the command prompt). Known interstitials (`[Pause]`, "Show today's
  log?", inactivity warnings) are auto-dismissed wherever they appear.
- **`tw ensure [target] --profile NAME` (B4):** idempotent — classifies
  the current screen and no-ops if already at `target`; otherwise runs
  the automaton's unmet suffix. Spawns the daemon first if none is
  running, so this single verb covers cold-start, mid-session, and
  post-drop recovery.
- **Reconnect + keepalive (D9/D10):** the daemon runs a background
  `SessionGuardian` that detects a dropped connection and auto-reconnects
  + replays login using the saved credential (the fix for a character
  lost to an idle-timeout drop with an unsaved password), and sends a
  conservative keepalive nudge only when idle **and** parked at the safe
  `main_command` screen — never on a password/trade/menu prompt.

## Watching it play — `tw spectate`

**`tw spectate` is a standalone command you run yourself, in your own
terminal, fully decoupled from whoever (or whatever) is driving.** It
attaches to the already-running daemon and renders the live game as a
pure observer — it doesn't start, control, or depend on any driving
process, and it needs zero cooperation from one.

**Quickstart — two terminals:**

```bash
# Terminal A — the driver (you, an agent, or an autopilot)
tw start --host <TW2002_HOST> --port 23
tw do "..." --wait-prompt "..."      # keeps driving, turn by turn

# Terminal B — yours, the spectator
tw spectate                          # live dashboard: watch it drive
```

That's the whole contract: start `tw spectate` any time after `tw start`
has connected, in a completely separate terminal. It doesn't matter who's
driving or how — a live Claude session issuing `tw do`, a future
autopilot, or a human typing `tw send` by hand. The spectator just
watches whatever settles. It survives the driver coming and going (every
`tw do`/`tw send` is its own short-lived one-shot process anyway — only
the daemon and your spectator connection are long-lived), and detaching
(Ctrl-C or `q`) never touches the daemon or the game session — it only
closes your own socket.

The underlying mechanism: the daemon detects "settle edges" (the screen
stopped changing AND is different from the last one it announced) and
pushes each one to every subscribed client — any number of spectators can
attach at once, and connecting mid-session immediately seeds you with the
current screen rather than making you wait for the next change.

```bash
tw spectate                          # THE deliverable: live interactive curses dashboard
tw spectate --snapshot --frames 3    # proof/scripting only — prints N frames to stdout, no curses
tw watch --json --frames 5           # raw JSON events, for scripting
```

Spectating is read-only — subscribing never sends input to the game.

## Taking the wheel — `tw attach`

**`tw attach` is the interactive companion to `tw spectate`.** Where
spectate is a passive dashboard, attach is a full-screen, real-color
terminal into the daemon's single game connection — your keystrokes go
straight to the game, one at a time and unbuffered (TW2002 reads most
menu commands a single keystroke at a time, so there's no local
line-editing to get in the way). You attach to whatever's already
running — no re-authenticating, no restarting anything.

```bash
tw attach                            # take the keyboard, play live, in color
```

**Control-lock:** exactly one controller drives at a time. The moment
`tw attach` connects, the daemon locks out the AI driver — any `tw
do`/`tw send` from elsewhere is rejected with
`controller_locked_by_human` (never silently interleaved onto the wire)
until you detach. `tw status` reports the current state as
`"mode": "ai_pilot"` or `"human"` — an **extensible mode enum**
(`twclient/control_lock.py`), not a bare boolean: room for `spectate`
(a paused/nobody's-driving state) and, later, `auto_loop` (the learned
skills driving solo) without a wire-format change — the seam for the
in-flight Trainer Control Panel. Non-exclusive modes are switchable via
a `set_mode` protocol verb; `human` stays reachable ONLY through `tw
attach`'s own connection-scoped take/release (never a plain mode-set —
nothing can clobber an active attach out from under you). A second `tw
attach` while one is already active is rejected immediately, before it
ever touches the terminal.

**`Ctrl-]`** (the classic telnet-client escape character) detaches and
hands control straight back to the AI — deliberately not `q`/`Ctrl-C`
like spectate's detach key, since those are live TW2002 menu commands
here (e.g. `Q` to quit) and would otherwise eat real game input.

`tw spectate` is unaffected either way — it never takes control, and
stays a pure read-only view regardless of who (AI or human) currently
holds the keyboard.

## The Trainer Control Panel — directing the automated client

**North-star: like an old-fashioned trainer.** The AI drives; while it
drives, the client learns the profitable loops (`tw record`/`tw
mine`/`tw play`'s existing engine); once a loop is learned, the client
can pilot it autonomously — the AI is the trainer, the client is the
trainee that graduates to solo flight. `tw spectate` gained a compact
**control strip** (mode badge + live TX readout + keybinding hints/a
progress bar) so the operator can direct all of this without leaving the
dashboard or typing CLI verbs.

**Note on "read-only":** the control strip's keybindings send
META-commands to the daemon's control plane (mode switches, starting/
stopping the background loop-player) — they no longer make `tw
spectate` *literally* read-only in the narrowest sense, but nothing here
ever forwards a keystroke to the game directly; every action is a
mode/loop-player transition the operator explicitly triggers. `tw attach` remains
the only thing that drives the game directly.

**Keybindings (inside `tw spectate`):**

| Key | Action |
|---|---|
| `M` | Cycle mode: `AI-PILOT` ↔ `SPECTATE`. (`AUTO-LOOP` is only entered via the Library below; `MANUAL` only via a separate `tw attach` — see control_lock.py's module docstring for why each exclusive mode has its own door, never a generic cycle.) |
| `L` | Open/close the **Learned-Loops Library** — browses every saved skill (name · source · profit metric · step count). `↑`/`↓` (or `j`/`k`) select, `1`-`9` set the cycle count to arm, `Enter` arms + starts the highlighted loop, `Esc`/`L` closes without starting. |
| `Space` | Pause/resume the running AUTO-LOOP (no-op if nothing's running). |
| `X` | Stop the running AUTO-LOOP — returns to `AI-PILOT`. |
| `P` | **Panic** — halts AUTO-LOOP (if any) and parks explicitly in `SPECTATE`, regardless of current state. |
| `q` / `Ctrl-C` | Detach (unchanged) — `Ctrl-C` always works immediately, even with the Library open. |

The mode badge is color-coded (info=AI-PILOT, ok=AUTO-LOOP, warn=MANUAL,
muted=SPECTATE); while AUTO-LOOP is running, the strip's right side
shows a live cycle-progress bar (`Playing <loop> ▸ 3/5 [██████░░]`)
instead of the hint legend, broadcast by the daemon's background
`LoopPlayer` over the same watch stream `tw spectate`/`tw watch` already
read (a `"play_progress"` event per cycle boundary) — unlike `tw play`,
which blocks the calling connection until the whole run completes with
no live view into it.

## Core transparency — the TX (sent-input) channel

**Every watch event now also carries `sent_input`** (and `cursor`, the
game's pyte cursor position) — Session.send()/send_raw()'s single TX
chokepoint, mirroring `build_response()`'s existing single RX chokepoint.
This means:
- `tw spectate`'s control strip shows a live `→ <last sent>` readout,
  and the event ticker pairs each row with its trigger (`main_command
  (idle) — Command...  →158`).
- `tw attach`'s status bar echoes the actual key just forwarded
  (`sent:12 → <Enter>`), and the caret now tracks the game's own cursor
  position instead of staying hidden.
- A `--secret` send's `sent_input` is the same `<redacted>` placeholder
  `tw history`/the ledger already use — never the real password text.

## Tests (network-free)

```bash
.venv/bin/python3 -m pytest tests/ -v
```

Covers IAC stripping/negotiation (including sequences split across
`recv()` boundaries), pyte render+crop (CP437 box-drawing decode), the
prompt classifier (synthetic anchors + real fixtures captured live in
`tests/fixtures/`), state extraction, settle-detection timing via a fully
fake clock (no real sleeping), the watch-stream's settle-edge/fan-out
logic, the spectator dashboard's pure layout functions, the credential
store (save/load/redaction/permissions), the login automaton (NEW
registration + password-mismatch-retry + RETURNING branches, D7
interstitials, `ensure` idempotence, stuck/retry-exhaustion failure
modes — all against an ordered-script fake session, no network), the
session guardian (D9 reconnect-replay + D10 idle-keepalive, including the
never-on-unsafe-screens guard), and `tw attach`'s control-lock (take on
connect, reject a second concurrent attach, reject/never-interleave a
`do`/`send` from the AI while human-held, always release on detach —
against a real unix socket + a fake session, plus a real pty proving an
actual keystroke reaches the game through curses).

## Known limitations (v1)

- `tw screen`/`tw do`/etc.'s plain-text CLI output stays color-stripped by
  design (token-efficient, plain-terminal-friendly). `tw spectate`'s MAIN
  pane DOES render the game's real ANSI colors (D13) — every event
  carries pyte's per-cell fg/bg/bold attribute map (`twclient/terminal.py`
  `color_map()`) alongside the plain text, and the spectator paints it via
  curses color pairs. Falls back to plain automatically if the terminal
  has no color support (`curses.has_colors()` is false).
- `state` parsing is a best-effort skeleton — extend the anchors in
  `twclient/state_parser.py` and `twclient/classify.py` as new screen
  shapes turn up in play.
- `tw stop`'s in-game QUIT is only attempted when the current screen
  classifies as `main_command`; on any other screen it just disconnects.
- A spectator that disconnects while idle (no screen change happening)
  isn't detected until the next real settle-edge tries to write to it —
  fine for interactive use, worth a heartbeat/ping if that ever matters.
- `tw attach`'s raw keystrokes are transcript-logged like any other TX
  bytes (`connection.py`'s `send_bytes()`), with **no redaction path** —
  unlike `do`/`send`'s `secret` flag. Not expected to matter in the
  normal flow (you attach to an already-logged-in session), but if a
  screen ever prompts for a password interactively mid-attach, those
  keystrokes land in `logs/session-<ts>.log` unmasked.
