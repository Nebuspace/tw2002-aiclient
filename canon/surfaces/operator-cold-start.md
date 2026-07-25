---
type: Surface
title: Operator Cold Start
description: Prescriptive day-to-day cold-start for the product TUI and ops CLI against the one daemon — profiles, secrets, Mode, run-dir isolation, and stuck-seat recovery.
tags: [surface, operator, cold-start, profiles, run-dir, cockpit]
timestamp: 2026-07-25T21:10:00Z
---

How an operator brings up the **human-piloted trainer** against the single-session daemon.
Architecture, Mode, Spectate/Attach, and secrets doctrine are owned by sibling concepts —
this surface is the **cold-start contract**: what to run, what never to put where, and how to
isolate or recycle a live seat. When prose here disagrees with [North Star](/architecture/north-star.md)
or [Secrets & Credential Handling](/doctrine/secrets-and-credentials.md), those win.

# Setup (once)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config/profiles.toml.example config/profiles.toml
```

Edit `config/profiles.toml` with **non-secret shape only** (server catalog name / host / port /
game letter / handle / optional ship & planet / allow-register / Autopilot). Passwords live in
`config/secrets.json` (chmod 600, gitignored) or `TW2002_PASSWORD_<PROFILE>` — never in argv,
`profiles.toml`, or logs. See [Secrets & Credential Handling](/doctrine/secrets-and-credentials.md).

# Launcher & create

```bash
./tw2002-aiclient   # needs a real TTY
```

Pick an existing profile, or **+ Create new profile** (catalog servers from `config/servers.toml`).
Retired rows are grey / unselectable. Public catalog provenance:
[Server Catalog Sources](/doctrine/server-catalog-sources.md).

**Password is deferred at create.** The create form does not ask for a password and never writes
one to `profiles.toml`. Before the first `ensure` / Play, supply credentials out-of-band:

| Source | How |
|---|---|
| Env (preferred for one-offs) | `TW2002_PASSWORD_<PROFILE>` — profile id uppercased, hyphens → underscores |
| Secrets file | `config/secrets.json` chmod 600: `{"<profile>": {"password": "…"}}` |

Resolver precedence on login: **env > secrets.json**. Returning characters need a stored
password before Play; new registration (`allow_register`) can generate and persist one via
ensure/login. Never pass a password on argv.

# Play / Mode / Spectate / Attach

Enter opens the framed cockpit. The client ensures the session (spawn daemon if needed, login
to the main command prompt). Live drivers are **App** (taught autopilot) or **Human**
(keyboard) — never an AI live driver. **Ctrl-A** is the Mode chord (ADR-002). Detach Human with
**Ctrl-]**. Details: [Spectate & Attach](/surfaces/spectate-and-attach.md) ·
[Mode Line & Teach Controls](/surfaces/mode-line-and-teach-controls.md).

Ops `./tw spectate` is **RETIRED / WONTBUILD**. Scripted settle-edge stream: `./tw watch`
([CLI Verb Surface](/architecture/cli-verbs.md)).

# Ops CLI (same daemon)

```bash
./tw status [--run-dir …] [--json]
./tw ensure --profile NAME [--run-dir …] [--no-auto-arm]
./tw attach [--run-dir …]          # Ctrl-] detach
./tw watch [--run-dir …]
./tw menumap …
./tw do "…" --run-dir …
./tw stop [--run-dir …]
```

Trust `./tw --help` and the root README for the live verb set; this concept does not inventory
every G-sequence landing.

# Run-dir isolation

Default socket/pid live under project `run/` (`twd.sock`, `twd.pid`). A second live seat needs
its own run directory.

| Mechanism | Example |
|---|---|
| Env | `TW_RUN_DIR=run/rogue ./tw2002-aiclient` |
| CLI flag | `./tw status --run-dir run/rogue` |

Relative paths resolve from the project root. Pass the same run dir to every verb for that seat.
`./tw status --json` reports `run_dir`.

# Recycle with `--no-auto-arm`

```bash
./tw stop --run-dir run/rogue
./tw ensure --profile rogue --run-dir run/rogue --no-auto-arm
TW_RUN_DIR=run/rogue ./tw2002-aiclient
```

`--no-auto-arm` skips post-ensure auto-start only for that `ensure` call.

# Live seat recovery

Inspect:

```bash
./tw status --run-dir run/rogue --json
./tw watch --run-dir run/rogue
```

| Signature | What you see |
|---|---|
| `game_select` | classification / Autopilot `stop_reason` is `game_select` |
| Tick-cap stop | Autopilot not running, `ticks_done` == 500, `stop_reason` `max_ticks_exhausted` |
| `explore_exhausted` | frontier idle stop |
| Intervention attention | `intervention.needs_attention` / STOP banner |
| Unanswered warp Y/N | `warp_confirm`; Autopilot may still show `running: true` while not sending |

Unanswered warp (manual clear):

```bash
./tw do "Y" --run-dir run/rogue    # or "N"
```

Then re-arm App, or hub-recycle with `--no-auto-arm` if wedged.

# Related

* [Entry & Profile Selection](/surfaces/entry-and-profile-selection.md)
* [CLI Verb Surface](/architecture/cli-verbs.md)
* [Server Catalog Sources](/doctrine/server-catalog-sources.md)
* [Secrets & Credential Handling](/doctrine/secrets-and-credentials.md)
