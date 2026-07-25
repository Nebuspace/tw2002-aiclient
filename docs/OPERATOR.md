# Operator guide

Day-to-day notes for the product TUI and the ops CLI against the same daemon.
**This file is not OKF canon** — architecture, Mode, Spectate/Attach, and
secrets doctrine live under [`canon/`](../canon/). CLI inventory and verb
status live in the root [`README.md`](../README.md). When they disagree,
prefer `canon/` + README.

## Product cold start

1. **Setup (once):** create the venv and copy a local profile file.

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp config/profiles.toml.example config/profiles.toml
   ```

   Edit `config/profiles.toml` with non-secret shape only (server catalog name /
   host / port / game letter / handle). Passwords stay in `config/secrets.json`
   (chmod 600, gitignored) or `TW2002_PASSWORD_<PROFILE>` — never in argv,
   profiles.toml, or logs.

2. **Launcher:** start the product TUI (needs a real TTY).

   ```bash
   ./tw2002-aiclient
   ```

   Pick an existing profile, or **+ Create new profile** (catalog servers from
   `config/servers.toml`). Retired rows are grey / unselectable.

   **Password is deferred at create.** The create-profile form collects only
   non-secret shape (id / server / game letter / handle / optional ship &
   planet / allow-register / Autopilot). It does **not** ask for a password and
   never writes one to `profiles.toml`. Before the first `ensure` / Play,
   supply credentials out-of-band:

   | Source | How |
   |---|---|
   | Env (preferred for one-offs) | `TW2002_PASSWORD_<PROFILE>` — profile id uppercased, hyphens → underscores (e.g. profile `my-lane` → `TW2002_PASSWORD_MY_LANE`) |
   | Secrets file | `config/secrets.json` chmod 600: `{"<profile>": {"password": "…"}}` |

   Resolver precedence on login: **env > secrets.json**. Returning characters
   need a stored password before Play; new registration (`allow_register`) can
   generate and persist one via the existing ensure/login path. Never pass a
   password on argv.

3. **Play / cockpit:** Enter opens the play shell (framed cockpit). The client
   ensures the session (spawn daemon if needed, login to the main command
   prompt using the env/secrets password path above).

4. **App / Human (Mode):** the live driver is **App** (taught autopilot) or
   **Human** (keyboard) — never an AI live driver. **Ctrl-A** is the Mode chord
   (ADR-002): from Spectate or App-hold it attaches Human; while attached it
   returns the seat to App. Bare `M` while attached is TradeWars Move, not Mode.
   Detach from Human with **Ctrl-]** (canon detach key). Details:
   [`canon/surfaces/spectate-and-attach.md`](../canon/surfaces/spectate-and-attach.md)
   · [`canon/surfaces/mode-line-and-teach-controls.md`](../canon/surfaces/mode-line-and-teach-controls.md).

5. **Spectate:** read-only watch is **in-cockpit Spectate** (product path).
   Ops `./tw spectate` is **RETIRED / WONTBUILD** (folded into the cockpit).
   For a scripted settle-edge stream use `./tw watch` (see README).

6. **Attach (human drive):** taking Human via Ctrl-A (or `./tw attach`) uses the
   daemon attach path. If Autopilot / App is running, attach **stops the runtime trainer**
   first (clears the live lock) so human drive can take the keyboard —
   it does **not** write profile `autopilot=` OFF (profile arm / disarm remains
   a separate control). If the runtime stop fails, attach cannot proceed.
   Detach with `Ctrl-]`; Esc may return toward the launcher depending on screen.

Play panels are read-only chrome; they never send game I/O. Only Human attach
(or ops `./tw do` / App autopilot) drives the connection.

## Ops CLI (same daemon)

```bash
./tw status [--run-dir …] [--json]
./tw ensure --profile NAME [--run-dir …] [--no-auto-arm]
./tw attach [--run-dir …]          # Ctrl-] detach
./tw watch [--run-dir …]           # NDJSON settle-edge stream (not full-curses HUD)
./tw menumap …
./tw do "…" --run-dir …
./tw stop [--run-dir …]
```

Further verbs (`loops`, …) land via the G-sequence work orders — not every
name on help is live yet; trust `./tw --help` and README over this file.

## Run-dir isolation (live seat)

Default daemon socket/pid live under project `run/` (`twd.sock`, `twd.pid`).
A second live seat needs its own run directory so it does not collide with the
default shared runtime.

| Mechanism | Example |
|---|---|
| Env (product + adapters) | `TW_RUN_DIR=run/rogue ./tw2002-aiclient` |
| CLI flag (ops) | `./tw status --run-dir run/rogue` |
| Ensure / attach / watch | `./tw ensure --profile rogue --run-dir run/rogue` |

Relative paths resolve from the project root. Always pass the same run dir to
every verb that talks to that seat. `./tw status --json` reports `run_dir` so
you can confirm which socket you hit — default `run/` may show
`daemon_running=false` while an isolated seat is live elsewhere.

## Recycle with `--no-auto-arm`

When recycling a live seat (stop daemon, restart to a new tip, re-ensure) and
you want connect/login **without** immediately arming App autopilot — even if
the profile has `autopilot=true`:

```bash
./tw stop --run-dir run/rogue
./tw ensure --profile rogue --run-dir run/rogue --no-auto-arm
# verify screen / classification, then arm when ready via the product path
TW_RUN_DIR=run/rogue ./tw2002-aiclient
```

`--no-auto-arm` skips post-ensure auto-start only for that `ensure` call.

## Live seat recovery

Current live ops seat often uses the isolated run dir **`run/rogue`**. Always
pass `--run-dir run/rogue` (or `TW_RUN_DIR=run/rogue`) on every `status` /
`ensure` / `attach` / `watch` / `stop` for that seat — default `run/` is a
different daemon.

### Failure signatures

Inspect with:

```bash
./tw status --run-dir run/rogue --json
./tw watch --run-dir run/rogue          # or in-cockpit Spectate attention chrome
```

| Signature | What you see |
|---|---|
| `game_select` | `classification` is `game_select`, and/or Autopilot `stop_reason` is `game_select` (door-select rejoin exhausted) |
| Tick-cap stop (legacy / explicit ceiling) | Autopilot not running, `ticks_done` == 500, `stop_reason` `max_ticks_exhausted` — not the continuous default |
| `explore_exhausted` | Autopilot `stop_reason` (or last decision reason) `explore_exhausted` — frontier idle, no hop |
| Intervention attention | `intervention.needs_attention` true — cockpit attention chrome / STOP banner when typed reasons apply |
| Unanswered warp Y/N | Prompt `Do you really want to warp there? (Y/N)` / `classification` `warp_confirm`; `idle_ms` rising; Autopilot still `running: true` (ticks may increment) but **not sending**. Tip `7dba009+` auto-answers on a recycled seat; keep this row for pre-tip binaries or any stuck gate |

Continuous Autopilot past 500 ticks with `running: true` is healthy under the
uncapped default; do not recycle solely because `ticks_done` exceeded 500.

### Recover

**Unanswered warp Y/N** (manual clear when Autopilot is spinning on the gate):

```bash
# stop runtime Autopilot / release App hold first if needed (Ctrl-A / product arm)
./tw do "Y" --run-dir run/rogue    # or "N" to decline the hop
# then re-arm App, or hub-recycle with --no-auto-arm if the seat is wedged
```

Hub recycle connect/login **without** auto-arming, verify, then re-arm:

```bash
./tw stop --run-dir run/rogue
./tw ensure --profile rogue --run-dir run/rogue --no-auto-arm
# confirm classification is main_command (not game_select), then re-arm:
TW_RUN_DIR=run/rogue ./tw2002-aiclient
```

Same `--no-auto-arm` sequence as [Recycle with `--no-auto-arm`](#recycle-with---no-auto-arm).

## Quick checklist

| Goal | Command / key |
|---|---|
| Product play | `./tw2002-aiclient` |
| Create profile (no password field) | launcher **+ Create** → then env/`secrets.json` before Play |
| Mode App ↔ Human | **Ctrl-A** (ADR-002); detach Human **Ctrl-]** |
| In-cockpit Spectate | product path (ops `./tw spectate` RETIRED) |
| Isolated live seat | `TW_RUN_DIR=run/rogue` or `--run-dir run/rogue` |
| Scripted watch stream | `./tw watch [--run-dir …]` |
| Human drive (ops) | `./tw attach` (`Ctrl-]` out) |
| Connect without Autopilot | `./tw ensure … --no-auto-arm` |
| Halt / stuck recovery | see **Live seat recovery** |
| Daemon health | `./tw status [--run-dir …] [--json]` |
| Clean shutdown | `./tw stop [--run-dir …]` |
| Architecture / doctrine | `canon/` (not this file) |
