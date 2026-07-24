# WO-03 — Play shell chrome (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Enter play mode and return to launcher without requiring a successful ensure (chrome path only).

**Scope:** `tw2002_aiclient/app.py` · `screens.py` (`run_play` layout shell)

**Depends-on:** WO-01 · at least one selectable profile (WO-02 optional)

**Accept:**
- Enter on an active profile opens `tw2002-aiclient — play` screen
- Header shows profile name; status line visible (ensure may say "failed" without creds — OK for this WO)
- Footer documents `h attach · a toggle Autopilot · Esc/q launcher`
- Esc or `q` returns to launcher loop (not process exit)

**Proof (TTY — creds optional):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# Enter on profile → see play chrome → Esc → back at launcher
```

**Out of scope:** Successful daemon ensure · live game screen · panel data freshness.

**Size:** ~15 min verify-only.

**Canon:** `canon/surfaces/trainer-cockpit.md` — play is pre-cockpit shell today; full frame is WO-10+

**Status:** **Shipped** (minimal chrome) — verify navigation contract.
