# WO-01 — Launcher smoke (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** See and navigate the profile launcher in a real terminal — thinnest path to product UI.

**Scope:** `tw2002_aiclient/screens.py` (`run_launcher`) · `tw2002_aiclient/adapters.py` (`list_launcher_rows`) — verify only unless Accept fails

**Depends-on:** WO-00

**Accept:**
- `./tw2002-aiclient` opens on branded header `tw2002-aiclient` and hint line `↑↓ select · Enter confirm · n new · q quit`
- At least one profile row **or** empty list with `+ Create new profile` row visible
- ↑/↓ moves selection marker `›`; retired profiles (if any) are dim and unselectable
- `q` or Esc returns to shell with clean exit (code 0)
- Footer mentions `./tw` ops CLI

**Proof (actual TTY — run interactively):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# ↑↓ move · q quit
```

Optional non-interactive guard:
```bash
.venv/bin/pytest tests/test_aiclient_adapters.py -k list_launcher -q
```

**Out of scope:** Enter → play · create form · daemon.

**Size:** ~15 min verify-only.

**Canon:** `canon/surfaces/entry-and-profile-selection.md` — player/profile picker

**Status:** **Shipped** — verify tonight before changing code.
