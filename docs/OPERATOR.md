# Operator guide

Short path for day-to-day use of the product TUI and the ops CLI against the
same daemon. For verbs and architecture, see the root [`README.md`](../README.md).

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

3. **Play:** Enter opens the play screen. The client ensures the session
   (spawn daemon if needed, login to the main command prompt using the
   env/secrets password path above) and syncs Autopilot to the profile flag.

4. **Autopilot toggle:** on the play screen, `a` or `Space` flips Autopilot
   ON/OFF and persists `autopilot=` on the profile. ON arms the trainer; OFF
   leaves you in manual / AI-pilot territory without the background loop.
   Default Autopilot is **continuous / uncapped** (no hidden 500-tick stop);
   an explicit max-ticks ceiling remains an optional ops safety valve.

5. **Attach (human drive):** `h` / `H` suspends play panels and hands the
   keyboard via the same engine as `./tw attach`. If Autopilot is running,
   attach **stops the runtime trainer** first (clears the live lock) so human
   drive can take the keyboard — it does **not** write profile `autopilot=`
   OFF (the play `a` / `Space` toggle still owns that). If the runtime stop
   fails, attach is blocked. Detach with `Ctrl-]`; play panels resume.
   Esc / `q` returns to the launcher.

Play panels are read-only chrome; they never send game I/O. Only attach (or ops
`./tw do` / Autopilot) drives the connection.

## Ops spectator

For a live read-only HUD (operators / scripts), use the backend CLI — not the
product TUI:

```bash
./tw spectate
./tw spectate --run-dir run/rogue    # when the seat uses an isolated run dir
./tw spectate --snapshot             # one-shot, scripting-friendly
```

`spectate` never forwards keystrokes to the game. Control-strip keys (mode,
loops, panic) are control-plane only; see the README spectator section.
`./tw attach` (or play-screen `h`) remains the human driver path.

## Run-dir isolation (live seat)

Default daemon socket/pid live under project `run/` (`twd.sock`, `twd.pid`).
A second live seat needs its own run directory so it does not collide with the
default shared runtime.

| Mechanism | Example |
|---|---|
| Env (product + adapters) | `TW_RUN_DIR=run/rogue ./tw2002-aiclient` |
| CLI flag (ops) | `./tw status --run-dir run/rogue` |
| Ensure / spectate / attach | `./tw ensure --profile rogue --run-dir run/rogue` |

Relative paths resolve from the project root. Always pass the same run dir to
every verb that talks to that seat (`status`, `ensure`, `spectate`, `attach`,
`stop`). `./tw status --json` reports `run_dir` so you can confirm which socket
you hit — default `run/` may show `daemon_running=false` while an isolated seat
is live elsewhere.

## Recycle with `--no-auto-arm`

When recycling a live seat (stop daemon, restart to a new tip, re-ensure) and
you want connect/login **without** immediately arming Autopilot — even if the
profile has `autopilot=true`:

```bash
./tw stop --run-dir run/rogue
./tw ensure --profile rogue --run-dir run/rogue --no-auto-arm
# verify screen / fighters / classification, then arm when ready:
./tw2002-aiclient   # with TW_RUN_DIR=run/rogue, toggle Autopilot ON
# or ops: start Autopilot via the product path / daemon autopilot_start
```

`--no-auto-arm` skips post-ensure auto-start only for that `ensure` call. Re-arm
explicitly after you confirm the seat is healthy.

## Live seat recovery

Current live ops seat uses the isolated run dir **`run/rogue`**. Always pass
`--run-dir run/rogue` (or `TW_RUN_DIR=run/rogue`) on every `status` / `ensure` /
`spectate` / `stop` for that seat — default `run/` is a different daemon.

### Failure signatures

Inspect with:

```bash
./tw status --run-dir run/rogue --json
./tw spectate --run-dir run/rogue    # paints ! strip when intervention.needs_attention
```

| Signature | What you see |
|---|---|
| `game_select` | `classification` is `game_select`, and/or Autopilot `stop_reason` is `game_select` (door-select rejoin exhausted) |
| Tick-cap stop (legacy / explicit ceiling) | Autopilot not running, `ticks_done` == 500, `stop_reason` `max_ticks_exhausted` — not the continuous default |
| `explore_exhausted` | Autopilot `stop_reason` (or last decision reason) `explore_exhausted` — frontier idle, no hop |
| Intervention attention | `intervention.needs_attention` true — spectate `! …` strip / play attention banner |
| Unanswered warp Y/N | Prompt `Do you really want to warp there? (Y/N)` / `classification` `warp_confirm`; `idle_ms` rising; Autopilot still `running: true` (ticks may increment) but **not sending**. Tip `7dba009+` auto-answers on a recycled seat; keep this row for pre-tip binaries or any stuck gate |

Continuous Autopilot past 500 ticks with `running: true` is healthy under the
uncapped default; do not recycle solely because `ticks_done` exceeded 500.

### Recover

**Unanswered warp Y/N** (manual clear when Autopilot is spinning on the gate):

```bash
# stop runtime Autopilot (product Play → Autopilot OFF, or daemon autopilot_stop)
./tw do "Y" --run-dir run/rogue    # or "N" to decline the hop
# then re-arm Autopilot, or hub-recycle with --no-auto-arm if the seat is wedged
```

Hub recycle connect/login **without** auto-arming Autopilot, verify, then
re-arm:

```bash
./tw stop --run-dir run/rogue
./tw ensure --profile rogue --run-dir run/rogue --no-auto-arm
# confirm classification is main_command (not game_select), then re-arm:
TW_RUN_DIR=run/rogue ./tw2002-aiclient   # Play → Autopilot ON
```

Same `--no-auto-arm` sequence as [Recycle with `--no-auto-arm`](#recycle-with---no-auto-arm);
use it whenever any signature above leaves Autopilot stopped or the seat
stuck off the main command prompt.

## Quick checklist

| Goal | Command / key |
|---|---|
| Product play | `./tw2002-aiclient` |
| Create profile (no password field) | launcher **+ Create** → then env/`secrets.json` before Play |
| Isolated live seat | `TW_RUN_DIR=run/rogue` or `--run-dir run/rogue` |
| Watch (ops) | `./tw spectate [--run-dir …]` |
| Human drive | play `h` or `./tw attach` (`Ctrl-]` out) |
| Connect without Autopilot | `./tw ensure … --no-auto-arm` |
| Live seat (current) | always `--run-dir run/rogue` / `TW_RUN_DIR=run/rogue` |
| Halt / stuck recovery | see **Live seat recovery** (`game_select`, tick-cap 500, `explore_exhausted`, `needs_attention`, unanswered warp Y/N) |
| Daemon health | `./tw status [--run-dir …] [--json]` |
| Clean shutdown | `./tw stop [--run-dir …]` |
