# WO-P1-013 — Create form validation

> Status: DONE — hub-Accepted ce261a7 (2026-07-24)
**Phase:** 1 · **Type:** harden · **Depends:** WO-P1-012
**Canon:** `canon/surfaces/entry-and-profile-selection.md` (The new-player flow — required fields)

**Goal:** Make the create-form fail loud, not silent, on invalid input — a missing `game_letter`, an
unresolvable `server` catalog key, or a duplicate profile name must be rejected before the write.

**Scope:** `tw2002_aiclient/screens.py` (create-form validation branch) — no change to the storage
layer itself.

**Accept:**
- Submitting with an empty `game_letter` is rejected inline; `config/profiles.toml` is not written.
- Submitting a `server` key not present in `config/servers.toml` is rejected inline (never silently
  falls back to a bare unresolved host).
- Submitting a profile `name` that already exists in `config/profiles.toml` is rejected inline
  (never silently overwrites the existing entry).
- A rejected submission leaves the operator on the form with the entered values intact (not reset to
  blank) so they can correct just the bad field.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient
# Create New Player -> leave game_letter blank -> submit -> inline rejection, no write
# Create New Player -> server key "not_a_real_key" -> submit -> inline rejection, no write
diff <(git show HEAD:config/profiles.toml.example) config/profiles.toml  # unaffected by rejected attempts
```
