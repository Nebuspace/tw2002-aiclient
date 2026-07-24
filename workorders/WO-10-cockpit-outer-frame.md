# WO-10 — Cockpit outer frame (build)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Wrap play screen in the bordered outer frame described in trainer-cockpit canon (character strip + three-column body + logs band).

**Scope:** `tw2002_aiclient/screens.py` (`run_play` layout) · new small layout helper if needed (keep file size sane)

**Depends-on:** WO-09

**Accept:**
- Visible cyan/bold outer border on ≥100×30 terminal (degrade gracefully ≥80×24 — no crash, no overlap)
- Top character strip region reserved (content from WO-09)
- Three-column body regions labeled or spaced for GOALS | center | HUD/DECISIONS even if center empty until WO-11
- Bottom `[LOGS]` band region reserved (content WO-12)

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# Enter play — resize terminal — frame intact
```

Optional: fake-pty geometry test if added.

**Out of scope:** Populating center game viewport · semantic colors (WO-15) · spectate_layout fork.

**Size:** ~1 sitting layout pass.

**Canon:** `canon/surfaces/trainer-cockpit.md` — frame ASCII diagram

**Status:** **Gap** — play screen is flat text today.
