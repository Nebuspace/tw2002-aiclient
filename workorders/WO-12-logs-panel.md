# WO-12 — LOGS panel (extend)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Full-width session transcript tail in the bottom `[LOGS]` band.

**Scope:** `tw2002_aiclient/adapters.py` (poll `tw log` or status transcript field) · `screens.py` logs region

**Depends-on:** WO-10 · WO-04

**Accept:**
- `[LOGS]` titled box shows last N human-readable ledger lines (≥5 visible on default terminal)
- New log lines appear without manual refresh beyond play poll loop
- Redaction: no password substrings from ledger (inherits twclient redaction)

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# drive one safe action via attach or autopilot tick → see log line appear
./tw log | tail -5
```

**Out of scope:** Full spectate log scroll UX · log search · file tail of raw twd stderr.

**Size:** ~1 sitting.

**Canon:** `canon/surfaces/trainer-cockpit.md` — bottom `[LOGS]` band · `canon/engine/trace-ledger.md`

**Status:** **Gap** — play shows short inline log snippet only.
