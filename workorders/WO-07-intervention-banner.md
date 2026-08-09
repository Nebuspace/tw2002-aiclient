# WO-07 — Intervention banner (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

> **Tip honesty (2026-08-09):** ops `./tw spectate` is **RETIRED / WONTBUILD** (Max · rebirth). Accept/Proof that require parity with or running `./tw spectate` are tip-false — live observation is in-cockpit Spectate ([Trainer Cockpit](../canon/surfaces/trainer-cockpit.md) · PWO-055) plus `tw watch`. Do not invent the ops verb.

**Goal:** When daemon reports `intervention.needs_attention`, play screen shows the same attention strip as spectate.

**Scope:** `tw2002_aiclient/adapters.py` (`intervention_from_status`, `compose_play_panels`) · `twclient/intervention_labels.py`

**Depends-on:** WO-06 · live session that can trigger intervention (or mocked test)

**Accept:**
- Healthy session: no banner row (omitted, not empty noise)
- `needs_attention: true`: bold banner line prefixed with `!` and human labels from reason codes
- Labels match in-cockpit Spectate / play stop-banner strip for same `status` JSON (ops `./tw spectate` RETIRED — do not use as Accept parity)
- Unknown reason codes degrade to raw code, not crash

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
.venv/bin/pytest tests/test_aiclient_play_panels.py tests/test_intervention_labels.py -q
# Live: provoke halt (autopilot error / manual status with intervention) and eyeball banner in play
./tw status --json | python3 -c "import sys,json; print(json.load(sys.stdin).get('intervention'))"
```

**Out of scope:** Teach hotkeys at escalation · AI analyze · fixing daemon intervention reasons.

**Size:** ~20 min verify (+ live eyeball if easy).

**Canon:** `canon/architecture/control-and-escalation.md` — enumerable STOP reasons

**Status:** **Shipped** — verify parity with in-cockpit Spectate / stop-banner (ops `./tw spectate` RETIRED).
