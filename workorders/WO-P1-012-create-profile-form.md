# WO-P1-012 — Create profile form

> Status: DONE — hub-Accepted f316c62 (2026-07-24)
**Phase:** 1 · **Type:** verify/build · **Depends:** WO-P1-010
**Canon:** `canon/surfaces/entry-and-profile-selection.md` (The new-player flow)

**Goal:** Build the Create New Player flow — pick a server from the `config/servers.toml` catalog,
name the character, and save a non-secret profile shape — with structurally no password field.

**Scope:** `tw2002_aiclient/screens.py` (create-form screen), wiring to `tw2002_aiclient/session/credentials.py`'s
`create_profile()` (stub from WO-P0-005, extended here to actually persist).

**Accept:**
- The form lets the operator choose a server by catalog key (never types a raw hostname) and enter
  `game_letter` + `handle`.
- Saving writes a new section to `config/profiles.toml` referencing the catalog `server` key, not a
  copied host/port.
- The form has **no password input field** anywhere in its widget tree — grep-verifiable, not just
  visually absent.
- A profile created via the form appears in the launcher list (WO-P1-010) on next open.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
grep -ni "password" tw2002_aiclient/screens.py     # expect no match in the create-form section
.venv/bin/python -m tw2002_aiclient
# Create New Player -> pick a catalog server, game letter B, handle NewPilot -> save
grep -A3 "\[scout" config/profiles.toml            # new section references server=<catalog key>
```
