# WO-06 — Live panels poll (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Play screen shows GOALS · FOCUS · DECISIONS panels that refresh from daemon `status` ~1 Hz.

**Scope:** `tw2002_aiclient/adapters.py` (`poll_status`, `compose_play_panels`, `goals_snapshot_from_status`) · `screens.py` (`run_play` draw loop)

**Depends-on:** WO-04

**Accept:**
- Metrics strip shows `Sector … Credits … Turns …` (may be `?` until parsed — not blank crash)
- Panel blocks labeled `— GOALS —`, `— FOCUS —`, `— DECISIONS —` render without overlap on ≥80×24 terminal
- Values change within ~2s when game state changes (manual `./tw do` in second terminal acceptable)
- Poll errors surface on status line, not exception traceback

**Proof (TTY + optional second terminal):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient   # enter play on live session
# watch panels update; or in another tty: ./tw do "I"  and watch credits/turns
.venv/bin/pytest tests/test_aiclient_play_panels.py -q
```

**Out of scope:** Full trainer-cockpit grid · chain bubbles · formations panel · game viewport.

**Size:** ~20 min verify-only.

**Canon:** `canon/surfaces/trainer-cockpit.md` — GOALS vs FOCUS split (partial implementation)

**Status:** **Shipped** (read-only compose via `spectate_layout`) — verify live.
