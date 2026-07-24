# WO-P2-020 — Ensure from play entry

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 2 · **Type:** verify/build · **Depends:** WO-P1-016
**Canon:** `canon/architecture/login-automaton.md`, `canon/architecture/session-engine.md`

**Goal:** Wire the play-shell hand-off (WO-P1-016) to actually spawn/reuse the daemon and drive an
idempotent `ensure` to the `main_command` class, replacing the placeholder play screen with a real
session wire.

**Scope:** `tw2002_aiclient/adapters.py` (new — `ensure_session()`), `tw2002_aiclient/session/cli.py` `ensure` verb
stub, `tw2002_aiclient/session/daemon.py` minimal daemon spawn.

**Accept:**
- Entering play with a credentialed profile runs `ensure` and the play shell reaches a state showing
  the daemon is connected and classified `main_command`.
- `run/twd.sock` and `run/twd.pid` exist under the project-rooted default `run/` directory (not a
  per-profile subdirectory unless `TW_RUN_DIR` is explicitly set).
- `tw status --json` from a second shell shows `ok: true` with the `main_command` classification
  after ensure completes.
- Play does not hang past a bounded timeout on "Ensuring session…" — a failure surfaces a typed
  error, not a silent stall.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
export TW2002_PASSWORD_<PROFILE>=...
.venv/bin/python -m tw2002_aiclient
# select profile -> play -> reaches connected/main_command
# second terminal:
.venv/bin/python -m tw2002_aiclient.session.cli status --json | python3 -m json.tool
ls -la run/twd.sock run/twd.pid
```
