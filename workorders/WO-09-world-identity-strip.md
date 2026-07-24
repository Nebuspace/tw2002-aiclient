# WO-09 — World identity strip (extend)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Launcher rows and play header show explicit `host · game-letter · character` per canon world identity.

**Scope:** `tw2002_aiclient/adapters.py` (row enrichment) · `screens.py` launcher + play header · `twclient/world_identity.py`

**Depends-on:** WO-01 · WO-03

**Accept:**
- Launcher row includes resolved hostname (from catalog) and game letter (already partial — add explicit character/handle column alignment per canon sketch)
- Play header line 2 shows `host · game · handle` derived from `world_id_from_profile()`, not profile id alone
- Broken profile row still shows `error` marker, not crash

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# eyeball launcher columns + play header after Enter
python3 -c "
from twclient import credentials, world_identity
p = credentials.load_profile('YOUR_PROFILE')
print(world_identity.world_id_from_profile(p))
"
```

**Out of scope:** Player bank rotation driver · world-model stores.

**Size:** ~1 sitting (~1–2 files, small layout tweak).

**Canon:** `canon/surfaces/entry-and-profile-selection.md` · `canon/engine/world-identity.md`

**Status:** **Gap** — data exists; presentation incomplete vs canon cockpit strip.
