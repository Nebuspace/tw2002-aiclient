# WO-P2-021 — Run-dir default policy

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020
**Canon:** `canon/architecture/session-engine.md` (Single-Connection Invariant)

**Goal:** Guarantee the daemon writes its pidfile+socket to the project-rooted default `run/`
directory regardless of caller CWD, with `TW_RUN_DIR` as the sole documented override — no surprise
per-profile subdirectory splintering the single-connection invariant.

**Scope:** `tw2002_aiclient/session/daemon.py` (run-dir resolution), a short note in `knowledge/` (or the
findings log from WO-P0-006) documenting the override.

**Accept:**
- Running `tw start`/`ensure` from an arbitrary CWD still writes `run/twd.pid`/`run/twd.sock` under
  the repo root, not the caller's CWD.
- With `TW_RUN_DIR` unset, no per-profile subdirectory is created under `run/` — one daemon, one
  `run/` home, matching the single-connection invariant.
- Setting `TW_RUN_DIR=/tmp/alt-run` redirects both pidfile and socket there, and a second daemon
  pointed at the default `run/` still refuses to start if one is already live (pidfile guard holds
  independently per run-dir).

**Proof:**
```bash
cd /tmp && "$(git rev-parse --show-toplevel)"/.venv/bin/python -m tw2002_aiclient.session.cli start --host <h> --port <p>
ls -la "$(git rev-parse --show-toplevel)"/run/twd.sock   # written to repo root, not /tmp
TW_RUN_DIR=/tmp/alt-run .venv/bin/python -m tw2002_aiclient.session.cli start --host <h> --port <p>
ls -la /tmp/alt-run/twd.sock   # override honored
```
