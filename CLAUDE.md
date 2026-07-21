# tw2002-aiclient — Project Context

An AI-native TradeWars 2002 telnet client: a persistent session daemon (`twd`) owns the ONE telnet
connection + a pyte-emulated terminal, and a stateless one-shot CLI (`tw`) is what a Bash-driving
LLM worker actually calls — one verb, one round trip, a settled screen back. It is explicitly
**not built for human play** except through two dedicated human-facing surfaces (`tw spectate`,
`tw attach`) layered on top of the same daemon.

## Doc canon (read in this order)

- **`DESIGN.md`** — the original v1 architecture spec: the CLI/daemon split, the unix-socket JSON
  protocol, and the settle-detection design. Still accurate for what it covers, but its verb table
  predates `ensure`/`spectate`/`attach`/`watch`/`autoloop`/`loops` — it is the foundation, not the
  full current spec.
- **`README.md`** — the quickstart: setup, the verb table, and the auto-login / spectate / attach
  walkthroughs. Good for "how do I run this," not the spec of record.
- The living canonical documentation is being established in `knowledge/` — treat it as
  authoritative for everything it covers once populated.

## Setup & commands

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # single dependency: pyte>=0.8.2
```

`./tw` and `./twd` are self-locating launcher scripts — an `sh` trampoline execs this project's
`.venv` python, so they run from anywhere by absolute path, no `source .venv/bin/activate` needed.
`twd` is normally spawned for you by `tw start`; you don't invoke it directly.

Daily-driver verbs (full table in `README.md`):

| Verb | What it does |
|---|---|
| `tw start [--host H --port P]` | Spawn the daemon, connect, negotiate, return the first settled screen. |
| `tw do "<input>" [--wait-prompt REGEX] [--json]` | **The primary verb.** Send input, wait until settled, return the new screen + `settled_reason`. |
| `tw screen [--json]` | Non-destructive: current settled screen, prompt, classification, state. |
| `tw status [--json]` | Daemon alive? connected? idle-ms? current classification. Always safe/read-only — check this before `tw start`/`tw stop` if you're unsure whether a session is already live. |
| `tw stop` | Best-effort in-game QUIT, disconnect, daemon exit. |

Test: `.venv/bin/python -m pytest tests/` — network-free, fake-clock/fake-session driven (500+
tests). One caveat: exactly two tests in `tests/test_spectate_app.py` are gated on the REAL
`run/twd.sock` existing (`skipif` otherwise) — with a live daemon up they attach a real read-only
spectator and can flake on whatever the live screen shows. Running the suite next to a live
session, `--deselect` those two (grep `SOCK_PATH.exists` in that file for the current node ids).
No linter is configured for this project (no `pyproject.toml`/`ruff.toml`/`.flake8`) — don't
invent a lint step.

## Architecture map (`twclient/`)

- `daemon.py` — `twd`, the session daemon; owns the one telnet connection, serves the JSON socket protocol.
- `cli.py` — `tw`, the one-shot CLI; every verb is connect → send JSON → read JSON line → disconnect.
- `connection.py` / `iac.py` — the raw telnet socket + IAC (Interpret As Command) negotiation handling.
- `session.py` — the live telnet+pyte state a daemon process owns; implements settle-detection bookkeeping.
- `terminal.py` — pyte-backed 80x25 terminal emulator + token-efficient cropped rendering.
- `settle.py` — settle detection (the reliability core): decides when a screen has stopped changing.
- `classify.py` — screen classification via regex anchors on the rendered text.
- `state_parser.py` — best-effort structured game-state extraction (credits/sector/turns/port/etc).
- `protocol.py` — the JSON verb protocol shared by the daemon's socket server and the CLI.
- `control_lock.py` — the control-mode state machine: who may drive the one game connection (`ai_pilot`/`human`/`spectate`/`auto_loop`).
- `credentials.py` — the live secure credential store. (The unimported `credstore.py` duplicate was deleted 2026-07-19 — TW-18.)
- `login.py` — the classification-driven login automaton (auto-login, NEW-vs-RETURNING branching).
- `guardian.py` — reconnect + login-replay on drop, plus conservative idle-keepalive.
- `haggle.py` — deterministic (no-LLM) auto-haggle for the port OFFER sub-dialogue.
- `ledger.py` / `skills.py` / `miner.py` — the pattern-learning substrate: trace ledger, macro record/replay, and a profit-miner that proposes learned patterns.
- `loop_player.py` — the background AUTO-LOOP driver for the Trainer Control Panel.
- `watch.py` — the settle-edge push-stream engine behind `tw watch`/`tw spectate`.
- `spectate_app.py` / `spectate_layout.py` — `tw spectate`, the read-only curses spectator dashboard (layout logic is pure/testable, separated from the curses I/O).
- `interactive_app.py` — `tw attach`, the interactive live console that takes the keyboard.
- `logging_util.py` — full session transcript logging, including the `log_redacted()` path every password send must use.

## Hard rules

- **Secrets never touch logs, argv, shell history, or the repo.** `config/secrets.json` is
  chmod-600 and gitignored; `TW2002_PASSWORD_<PROFILE>` env var is checked first. Every password
  send must route through `logging_util.py`'s `log_redacted()`. Never echo, log, or return a
  password in any CLI response.
- **Single-connection, single-session daemon.** `run/twd.sock` + `run/twd.pid` live under this
  project directory regardless of the caller's CWD. The daemon refuses a second daemon via the
  pidfile; `control_lock.py` governs who may drive the one game connection — don't bypass it.
- **`config/`, `run/`, `state/`, `logs/` are all gitignored.** The only tracked files under
  `config/` are `config/profiles.toml.example` and `config/servers.toml` (the public game-server
  catalog resolved by `tw servers list`); real `profiles.toml` and `secrets.json` are local-only.
- **`wait_prompt` regexes are case-sensitive** (`settle.py` has no `re.IGNORECASE`) — a
  case-mismatched prompt regex silently times out instead of erroring.
- **`state_parser.py` anchors to the LAST match in the buffer, not the first** — this is
  deliberate (fixes a real stale-scrollback bug); don't "simplify" it back to first-match.

Local development/agent configuration lives in the gitignored `CLAUDE.local.md`.
