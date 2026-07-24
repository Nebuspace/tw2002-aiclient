# WO-15 — Semantic colors (polish)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Apply shared ok/warn/danger/info/muted palette to product TUI chrome consistently with spectate.

**Scope:** `tw2002_aiclient/screens.py` · small shared color helper (import from or mirror `spectate_app._SEMANTIC_COLORS` — avoid duplication drift)

**Depends-on:** WO-10

**Accept:**
- Intervention banner uses `warn` tone; Autopilot badge uses ok/warn; errors use danger
- Outer frame chrome uses cyan bold per ui-polish-assessment
- ASCII fallback when colors unavailable (no crash on monochrome)
- Product TUI matches spectate meaning for same semantic events where both show them

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# trigger intervention + toggle autopilot — colors readable
.venv/bin/pytest tests/test_aiclient_play_panels.py -q
```

**Out of scope:** Game viewport pyte colors (native — WO-11) · light theme.

**Size:** ~1 sitting polish.

**Canon:** `.samantha/plans/ui-polish-assessment.md` — 7-tone table

**Status:** **Gap** — product shell mostly plain curses attrs today.
