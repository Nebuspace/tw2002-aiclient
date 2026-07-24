# WO-16 — Player bank touchpoint (extend)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Show credential-bank rotation touchpoint and no-collusion boundary on entry surface.

**Scope:** `tw2002_aiclient/adapters.py` (wrap `player_bank` list) · `screens.py` launcher footer or sub-panel

**Depends-on:** WO-01

**Accept:**
- Launcher shows one-line bank summary OR `b` opens read-only bank list (name · handle · host · game · last_played)
- Visible boundary text: rotation multiplies operator's own turns; **never** transfer credits/cargo between characters
- Bank view metadata-only — no password fields
- `tw players list` parity for row content

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# b or footer bank summary
./tw players list
```

**Out of scope:** Automated rotation driver (daemon-side · QUEUE / canon divergence) · adding bank entries from TUI (CLI `tw players add` OK as doc-only).

**Size:** ~1 sitting.

**Canon:** `canon/surfaces/entry-and-profile-selection.md` — multi-player rotation touchpoint

**Status:** **Gap** — CLI verbs exist; product launcher does not surface bank.
