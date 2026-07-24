# WO-05 — Autopilot toggle (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Toggle Autopilot ON/OFF in play, sync runtime, and persist to `profiles.toml`.

**Scope:** `tw2002_aiclient/adapters.py` (`toggle_autopilot_and_sync`, `arm_autopilot`, `stop_autopilot`) · `screens.py` play key handler

**Depends-on:** WO-04 (daemon alive at command prompt)

**Accept:**
- `a` or Space flips reverse-video `[Autopilot ON|OFF]` badge on play screen
- `config/profiles.toml` `autopilot = true/false` updates immediately after toggle
- With daemon live: `./tw status --json` reflects autopilot running/stopped within one refresh
- Toggle message includes `saved`; failed runtime sync surfaces error on status line (not silent)

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# Enter credentialed profile → a → see ON → a → OFF
grep autopilot config/profiles.toml
./tw status --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('autopilot'))"
```

Tests:
```bash
.venv/bin/pytest tests/test_aiclient_adapters.py -k toggle_autopilot -q
```

**Out of scope:** Reborn App/Human mode line (`M` key) · taught-behavior arm-confirm gate (canon divergence on daemon autopilot — record, don't fix here).

**Size:** ~20 min verify-only.

**Canon:** `canon/architecture/app-autopilot-model.md` (prescriptive) · `control-and-escalation.md`

**Status:** **Shipped** — product uses Trainer Autopilot ON/OFF language per README.
