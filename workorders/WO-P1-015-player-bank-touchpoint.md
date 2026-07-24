# WO-P1-015 — Player bank touchpoint

> Status: DONE — hub-Accepted 75b5b31 (2026-07-24)
**Phase:** 1 · **Type:** extend · **Depends:** WO-P1-010
**Canon:** `canon/surfaces/entry-and-profile-selection.md` (Multi-player rotation touchpoint, The
hard boundary), `canon/doctrine/secrets-and-credentials.md` (The Credential Bank)

**Goal:** Surface the credential-bank rotation list on the launcher (a footer line or a `b` key) with
its no-collusion boundary text shown, never buried — matching the metadata-only bank.

**Scope:** `tw2002_aiclient/screens.py` (launcher footer/bank-view), wiring to `tw2002_aiclient/session/player_bank.py`
(stub reads only; the rotation driver itself is out of scope per canon's own code-divergence note).

**Accept:**
- A footer line or dedicated `b` view lists banked characters with `last_played`/`turns_state`,
  matching `tw players list`'s existing column shape.
- The boundary text — rotation multiplies the operator's own turns across independent characters;
  never collusion or resource-transfer between them — is displayed at this touchpoint, not just in
  canon prose.
- No password or password-shaped field appears anywhere in the bank view (the bank is metadata-only
  by construction).
- An empty/never-rotated bank entry shows the honest `never`/`-` sentinels, not a fabricated
  timestamp.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient
# press b (or view the footer) -> banked characters listed with the boundary text visible
grep -ni "password" tw2002_aiclient/screens.py   # bank-view section still has no password field
```
