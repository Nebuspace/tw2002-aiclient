# WO-08 — Human attach (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** From play, `h` hands keyboard via attach engine and returns to play panels on detach.

**Scope:** `tw2002_aiclient/adapters.py` (`suspend_and_attach`, `run_attach`) · `screens.py` play key `h`

**Depends-on:** WO-04

**Accept:**
- `h` suspends product curses and opens interactive attach (same engine as `./tw attach`)
- Typing reaches game; Ctrl-] (or attach detach convention) returns to play chrome
- If Autopilot was running, attach stops runtime trainer first; profile `autopilot` flag unchanged unless user toggled separately
- Failed attach shows message on play status line; curses restored (no broken terminal)

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# play → h → type a safe key (e.g. I at command) → detach → panels visible again
.venv/bin/pytest tests/test_aiclient_adapters.py -k attach -q
```

**Out of scope:** Reborn `M` mode toggle · spectate read-only path · profile Autopilot write on attach.

**Size:** ~25 min verify-only.

**Canon:** `canon/surfaces/spectate-and-attach.md` — attach takes control lock MODE_HUMAN

**Status:** **Shipped** — verify on live daemon.
