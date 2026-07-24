# WO-13 — Mode line App/Human (extend)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Replace legacy `ai_pilot` mode strings with reborn **App / Human** actor badge on play control strip.

**Scope:** `tw2002_aiclient/adapters.py` (`compose_play_panels` mode field) · `screens.py` control strip · map from `tw status` control mode

**Depends-on:** WO-06

**Accept:**
- Mode badge reads `App` when trainer/autopilot holds lock and `Human` after attach / human control
- No user-visible "AI pilot" or third mode slot
- Autopilot ON/OFF badge remains separate from actor badge (Trainer toggle ≠ actor — see README)
- Spectate attach-only sessions unchanged (`./tw spectate` ops path)

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# play with Autopilot ON → App · h attach → Human · detach → App or Human per status
grep -i 'ai_pilot' tw2002_aiclient/screens.py tw2002_aiclient/adapters.py  # expect none in user strings after WO
```

**Out of scope:** `M` key toggle (may stay attach-based until dedicated handler) · teach overlay badge.

**Size:** ~1 sitting.

**Canon:** `canon/surfaces/mode-line-and-teach-controls.md` — dual not triad

**Status:** **Gap** — panels still expose daemon mode vocabulary.
