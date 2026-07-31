# WO-EXPLORE-GATE-LIVE-PROVE — live audit

**UTC start:** 2026-07-31T14:24:38Z · **UTC end:** 2026-07-31T14:26:28Z · **Seat:** impl-aiclient-cursor · **PR #294**
**Tip:** `0169fc9` · **Proof home:** `.samantha/audit/explore-gate-live-20260731T1424Z/`
**Arm:** map-fill `min_sectors=0` · `turn_budget=12` · `--no-dock-new-ports` · `--no-fight-tolls` · Max sacrificial GO (WO)

## Tip-check E1–E4
- See `tip-check.txt` in this audit dir (E1 exhaustive min_sectors==0 · E2 port persistence · E3 map_fill/find_stardock · E4 never_auto).

## Diversity matrix

| host key | profile | class | ensure | explore | distinct before→after | reason | port.class after | pairs reason |
|---|---|---|---|---|---|---|---|---|
| `gone_rogue` | scout_rogue | RETURNING | PASS (main_command) | start_ok=True | 0→8 (fs=8) | `explore_exhausted:turn_budget` | 1 | fewer_than_two_ports |
| `academy_of_tradewars` | scout_academy | RETURNING | PASS (main_command) | start_ok=True | 0→9 (fs=9) | `explore_exhausted:turn_budget` | 6 | rc=0 |
| `a_net_online` | proof_anet_new | NEW | PASS (main_command) | start_ok=True | 0→8 (fs=8) | `explore_exhausted:turn_budget` | 5 | rc=0 |
| `microblaster_network` | scout_microblaster | RETURNING | SKIP ensure=fighter_encounter | start_ok=None | None→None | `—` | — | — |

## Counts
- hosts exercised **3** · NEW **1** · RETURNING **2** · SKIP **1** · FAIL **0**
- growth (distinct↑) **3/3** · port.class≥1 **3/3**
- Leak-safe port.class via indexed filesystem count (slug never printed).
- No secrets / handles / FQDNs / world slug paths in this STATUS-facing summary.

## Explicit non-claims
- Did not require port.commodities
- Not claiming #283 money-path diversity

