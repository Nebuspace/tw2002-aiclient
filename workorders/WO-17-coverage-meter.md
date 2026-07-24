# WO-17 — Coverage meter (build)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Read-only strip showing taught-coverage vs escalation frequency (reborn win metric).

**Scope:** `tw2002_aiclient/adapters.py` (derive from status/autopilot_trace/ledger counts) · `screens.py` HUD region

**Depends-on:** WO-06 · TW-05 actor attribution on daemon (partial — degrade gracefully)

**Accept:**
- HUD or strip shows ratio label per `canon/engine/coverage-metrics.md` (e.g. `% taught handling` or ticks without escalation)
- When ledger lacks actor fields, show `?` not fake precision
- Updates on play poll loop

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# run session with autopilot ticks → meter moves
./tw status --json | python3 -m json.tool | grep -E 'autopilot|trace'
```

**Out of scope:** Changing daemon ledger schema · coaching content.

**Size:** ~1 sitting.

**Canon:** `canon/engine/coverage-metrics.md` · `canon/architecture/north-star.md`

**Status:** **Gap** — spectate may show related metrics; product play does not.
