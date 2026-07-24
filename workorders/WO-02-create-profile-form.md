# WO-02 — Create profile form (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Create a non-secret profile from the launcher and see it listed — no password on this surface.

**Scope:** `tw2002_aiclient/screens.py` (`run_create_form`, `_save_form`) · `adapters.create_profile` · `config/profiles.toml` (gitignored live file)

**Depends-on:** WO-01

**Accept:**
- From launcher: `n` or select `+ Create new profile` opens form titled `new profile`
- Server picker cycles `config/servers.toml` keys (not free-text hostname)
- `s` save writes a section to `config/profiles.toml` with **no password field**
- New row appears in launcher after save; Autopilot checkbox persists
- Cancel Esc returns to launcher without write

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# n → fill Profile id + server + game letter + handle → s save → see new row
grep -A6 '^\[your_test_id\]' config/profiles.toml   # adjust name; confirm no password key
```

Unit guard:
```bash
.venv/bin/pytest tests/test_aiclient_adapters.py -k create_profile -q
.venv/bin/pytest tests/test_credentials.py -q
```

**Out of scope:** Password collection · first `ensure` / login · player bank.

**Size:** ~20 min verify-only.

**Canon:** `canon/surfaces/entry-and-profile-selection.md` — new-player flow · secrets deferred

**Status:** **Shipped** — verify; harden only if validation UX fails Accept.
