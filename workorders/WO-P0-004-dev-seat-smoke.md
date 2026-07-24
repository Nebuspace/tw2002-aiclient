# WO-P0-004 — Dev seat smoke

> Status: DONE — hub-Accepted 4554eb3 (2026-07-23)
**Phase:** 0 · **Type:** verify · **Depends:** WO-P0-003
**Canon:** `canon/architecture/cli-verbs.md`

**Goal:** Confirm the freshly scaffolded seat is runnable end to end — help text resolves, and the
TTY gate from WO-P0-003 holds — before any real verb or screen is built on top of it.

**Scope:** No new code; this is a verify-only WO exercising the WO-P0-003 scaffold plus a minimal
`--help` argument-parser stub in `tw2002_aiclient/session/cli.py` (the `tw` entry point stub, empty verb table).

**Accept:**
- `tw --help` (or `python -m tw2002_aiclient.session.cli --help` if the launcher script isn't wired yet) prints
  usage text and exits 0.
- The non-TTY exit-2 gate from WO-P0-003 still holds after this stub is added (regression check).
- No verb in the printed help table claims to do anything beyond what WO-P0-003 shipped — an empty
  or placeholder verb list is correct at this stage.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient.session.cli --help; echo "exit=$?"      # expect exit=0
echo | .venv/bin/python -m tw2002_aiclient; echo "exit=$?"   # expect exit=2 (still gated)
```
