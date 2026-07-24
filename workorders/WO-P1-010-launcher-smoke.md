# WO-P1-010 — Launcher smoke

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 1 · **Type:** verify · **Depends:** WO-P0-004
**Canon:** `canon/surfaces/entry-and-profile-selection.md`

**Goal:** See the branded pre-cockpit launcher for the first time in the greenfield build — the
player/profile picker renders, arrow-key navigation moves the selection, and `q` exits cleanly.

**Scope:** `tw2002_aiclient/screens.py` (launcher screen only), `tw2002_aiclient/app.py` (curses
router entry into the launcher). No create-form, no daemon wire, no world-identity columns yet.

**Accept:**
- Launching in a real TTY shows a titled launcher list (may be empty — see WO-P1-011 for the empty
  state) without raising.
- ↑/↓ moves the selection between rows when at least one profile exists.
- `q` exits the launcher and returns the terminal to a clean state (no leftover curses artifacts).
- No password field or password-shaped value is rendered anywhere on this screen (structural
  absence per entry-and-profile-selection's password-never-shown affordance).

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient
# navigate ↑↓ across rows (or the empty-state CTA), then press q — terminal returns clean
```
