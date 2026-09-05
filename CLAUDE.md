# tw2002-aiclient — project context

A **human-piloted trainer** for TradeWars 2002 (raw telnet BBS game). The operator flies; the
app carries only screens it has been *taught* (deterministic autopilot/macros). An AI teacher
may propose draft rules when invited, after the fact. **The AI never live-drives** a real
account — one narrow carve-out in `canon/doctrine/dev-drive-exception.md` (agent-authored
dev/debug proof only, sacrificial profile, never for play).

## Doc canon — read in this order

1. `canon/index.md` — OKF bundle entry point: `architecture/`, `engine/`, `surfaces/`,
   `doctrine/`, `strategy/`, `ADR/` (decisions), `DECISIONS.md` (open questions), `log.md`.
2. `workorders/README.md` — the live, ordered build queue; each WO has
   Goal · Scope · Constraints · Accept · Proof · Refs. Work proceeds **only** through this
   queue — don't freelance outside a WO's scope.
3. Code vs. canon disagree → canon wins; flag the drift, don't silently pick one.

## Setup & commands

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pip install -e .

./tw2002-aiclient          # product TUI (needs a real TTY)
./tw                       # one-shot CLI entry point
./twd                      # session daemon (normally spawned by `tw start`)

.venv/bin/python -m pytest              # parallel by default (-n auto); -n0 for serial debug
.venv/bin/python -m pytest -m "not live_login and not pty_ui"   # matches CI (.github/workflows/suite.yml)
```

No lint is configured — don't invent one. `live_login` needs a real server and doesn't run in CI;
`pty_ui` needs a real curses-capable pty and self-skips otherwise. Never run `tw start`/`tw stop`
against a session someone else may be driving — check `tw status` first.

## How work lands

Branch per work order (`wo/<ID>`) off `main` → PR → CI (`.github/workflows/suite.yml`) green,
including the zero-skipped-tests guard → merge. This tree is worked by more than one agent:
**commit only explicit paths** (`git commit -- <paths>`), never `git add -A` / `git add .`, and
never `git stash` — each can sweep or discard a sibling session's in-flight files, and both have
actually happened here. No force-push or history rewrite without sign-off.

## Secrets and credentials

Secrets never touch logs, argv, shell history, or the repo — see
`canon/doctrine/secrets-and-credentials.md`. `config/secrets.json` is chmod-600 and gitignored;
resolve passwords via `TW2002_PASSWORD_<PROFILE>` env-first; every send routes through the
redaction sink. **Public repo:** no real personal names, handles, FQDNs, or usernames committed.

## Path-leak gate

Committed content must never carry an operator-home absolute path (`/Users/<user>/` or
`/home/<user>/`). Cursor's `.cursor/hooks.json` → `.cursor/hooks/path-leak-gate.sh` is
`failClosed: false` by design (a worker host that can't run shell hooks stays usable). The
load-bearing backstop is `git config core.hooksPath scripts/githooks` **once per clone**, which
wires `scripts/githooks/pre-commit` → `scripts/path-leak-scan.sh` and fails closed: a staged
leak makes `git commit` exit 1 with HEAD unmoved. Claude Code enforces the same intent via its
own PreToolUse hook.

## Local orchestration is not shippable client code

`.claude/` and `.samantha/` are gitignored — local agent-framework install state, not product
code. Never let their contents leak into a commit.
