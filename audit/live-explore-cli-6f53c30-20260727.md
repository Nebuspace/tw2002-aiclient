# Live prove — `tw explore` CLI on tip `6f53c30`

**Seat:** orchestrator · **UTC:** 2026-07-27T01:28Z  
**Tip:** `origin/main` `6f53c30` (PR #59 — `WO-EXPLORE-CLI-INVOKE`)  
**Bank:** `/tmp/tw2002-live-ensure-matrix-20260726T0801Z` (ephemeral; never commit)  
**Wave:** `…/reprove/explore-cli-6f53c30/`

No credentials, handles, or screen dumps in this file. Public hostnames only.

## Result

| Step | Command surface | Result |
|---|---|---|
| ensure | `tw ensure --profile proof_micro` | `ok:true` · `classification=main_command` |
| explore start | `tw explore start --world-id microblaster_network --min-sectors 5` | `ok:true` · `started:true` |
| explore done | `tw explore status` | `outcome=completed` · **`distinct_sectors=5`** · ~4s |

## Max try recipe (RETURNING on a known-good host)

```bash
cd tw2002-aiclient
git pull --ff-only   # tip ≥ 6f53c30
# point TW_CONFIG_DIR at YOUR config (profiles with host + game_letter)
export TW_CONFIG_DIR=…   # your bank
export TW_RUN_DIR=run/try-explore   # or --run-dir each time

./tw ensure --profile <your_profile> --run-dir "$TW_RUN_DIR" --json
# wait until classification is main_command

./tw explore start --world-id <server_world_slug> --min-sectors 5 --run-dir "$TW_RUN_DIR" --json
./tw explore status --run-dir "$TW_RUN_DIR" --json   # until outcome completed|halted
./tw stop --run-dir "$TW_RUN_DIR"
```

**Notes**
- `world_id` is the world-model slug (hub used `microblaster_network` for micro).
- Autopilot still halts on `game_select` — this path is **ensure → explore**, not walkaway Autopilot.
- Ephemeral Proof* bank ≠ your profiles; create/use your own.

## Honesty

This closes the **CLI invoke gap** for M4 on one host (micro) on tip `6f53c30`. Multi-host explore + cockpit wire remain follow-ons, not blockers for a first Max try on a proved host.
