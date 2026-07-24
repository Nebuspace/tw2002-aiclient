# WO-00 — Dev seat smoke
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Confirm the product entrypoint runs on this machine before any UI work.

**Scope:** `tw2002-aiclient/` repo root · `.venv` · `./tw2002-aiclient` · `./tw`

**Depends-on:** —

**Accept:**
- `.venv/bin/python` imports `tw2002_aiclient` without error
- `./tw2002-aiclient --help` prints product description mentioning profile launcher / Autopilot
- `./tw2002-aiclient` **without TTY** exits 2 with "needs a real terminal"
- `./tw --help` lists backend verbs (`ensure`, `status`, `spectate`)

**Proof (TTY + non-TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
python -c "import tw2002_aiclient; print('ok')"
./tw2002-aiclient --help | head -5
./tw2002-aiclient 2>&1 | grep -i tty
./tw --help | grep -E 'ensure|status|spectate'
```

**Out of scope:** Daemon start · live game login · profile creation.

**Size:** ~10 min verify-only.

**Canon:** `canon/architecture/cli-verbs.md` (product vs ops split)
