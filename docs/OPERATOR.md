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
   (chmod 600, gitignored) or `TW2002_PASSWORD_<PROFILE>` — never in argv or logs.

2. **Launcher:** start the product TUI (needs a real TTY).

   ```bash
   ./tw2002-aiclient
   ```

   Pick an existing profile, or **+ Create new profile** (catalog servers from
   `config/servers.toml`). Retired rows are grey / unselectable.

3. **Play:** Enter opens the play screen. The client ensures the session
   (spawn daemon if needed, login to the main command prompt) and syncs
   Autopilot to the profile flag.

4. **Autopilot toggle:** on the play screen, `a` or `Space` flips Autopilot
   ON/OFF and persists `autopilot=` on the profile. ON arms the trainer; OFF
   leaves you in manual / AI-pilot territory without the background loop.

5. **Attach (human drive):** `h` / `H` suspends play panels and hands the
   keyboard via the same engine as `./tw attach`. Prefer Autopilot OFF first —
   a running trainer holds the control lock and attach is refused. Detach with
   `Ctrl-]`; play panels resume. Esc / `q` returns to the launcher.

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

## Quick checklist

| Goal | Command / key |
|---|---|
| Product play | `./tw2002-aiclient` |
| Isolated live seat | `TW_RUN_DIR=run/rogue` or `--run-dir run/rogue` |
| Watch (ops) | `./tw spectate [--run-dir …]` |
| Human drive | play `h` or `./tw attach` (`Ctrl-]` out) |
| Connect without Autopilot | `./tw ensure … --no-auto-arm` |
| Daemon health | `./tw status [--run-dir …] [--json]` |
| Clean shutdown | `./tw stop [--run-dir …]` |
