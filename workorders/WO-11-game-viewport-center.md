# WO-11 — Game viewport center (build)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

> **Tip honesty (2026-08-09):** ops `./tw spectate` is **RETIRED / WONTBUILD** (Max · rebirth). Accept/Proof that require parity with or running `./tw spectate` are tip-false — live observation is in-cockpit Spectate ([Trainer Cockpit](../canon/surfaces/trainer-cockpit.md) · PWO-055) plus `tw watch`. Do not invent the ops verb.

**Goal:** Embed the live 80×25 color game screen in the play cockpit center column.

**Scope:** `tw2002_aiclient/screens.py` · tip GAME viewport lives under `tw2002_aiclient/cockpit/` (historical Accept cited archive `twclient/spectate_app.py` / `terminal.py` — ops spectate RETIRED; do not revive)

**Depends-on:** WO-10 · WO-04

**Accept:**
- Center column shows native 80×25 game grid with zero inset (82×27 bordered viewport per canon)
- Colors match in-cockpit GAME viewport for same session (pyte color map; ops `./tw spectate` RETIRED)
- Viewport updates on play refresh cadence (~1 Hz) without stealing attach keyboard
- Disconnected state: border flips warn/danger per ui-polish-assessment (optional stub if no socket)

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# Enter live session — watch game screen animate in center while side panels update
# Compare in-cockpit Spectate / GAME viewport (ops ./tw spectate RETIRED — do not run)
```

**Out of scope:** Chain bubble row · HUD sticky freshness logic (cockpit helpers; not deleted spectate_*) · attach input routing through product frame.

**Size:** ~1–2 sittings (largest build WO).

**Canon:** `canon/surfaces/trainer-cockpit.md` — `[GAME UI]` zero-inset viewport

**Status:** **Gap** — major missing piece vs canon cockpit.
