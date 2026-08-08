# WO-WIRE-SHIP-UPGRADE-DEFENSE-FLOOR-HOSTILE-INPUT

**Status:** CLOSED · NO-CANON · tip verify `origin/main` `7b15a7e` · 2026-08-08T14:08:55Z
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/WIRE-SHIP-UPGRADE-DEFENSE-FLOOR-HOSTILE-INPUT` (docs-only close)
**Refs:** queue-aiclient.md Gate #3 · `ship_upgrade_decision.py:47,152,439` ·
`canon/strategy/ship-progression.md` § Defense floor

## Verdict

**CLOSED — no honest product wire without inventing.** Gate #3
(`defense_floor`) stays dormant until canon names a verified source for
**server-level** hostile/PvP posture.

## Verify-first (tip `7b15a7e`)

| Claim | Evidence |
|---|---|
| Engine gate exists | `evaluate_candidate`: `if state.hostile_or_pvp and ship.fighters < defense_floor_fighters` → `defense_floor` (`ship_upgrade_decision.py:152`) |
| Status plumb reads only | `upgrade_player_from_status` → `"hostile_or_pvp": status.get("hostile_or_pvp") is True` (`:439`) — **reader, not writer** |
| Zero product writers | `git grep hostile_or_pvp` on tip: only `ship_upgrade_decision.py` (field + reader + `PlayerState` rebuild) and `tests/test_ship_upgrade_decision.py` constructions. No protocol/session/status producer. |
| Archive also caller-kwarg only | Pre-rebirth `autopilot.assess(..., hostile_or_pvp=False)` threaded a default; never derived from screen/parser. |
| Canon scope = **server** | ship-progression: "On a hostile / PvP **server**" — not per-sector density / route fighters. |

## Rejected false wires (do not ship)

1. **Density `fighter_presence_hypothesis`** — explicitly `HYPOTHESIS`; `world_model.write_density_scan` must **never** mutate `threats` / feed route-hazard STOP. Parent constraint: do not invent HYPOTHESIS density into threats.
2. **Sector `threats.fighters` / `route_hazard_for_hop`** — verified STOP inputs for **planned hops**, wrong semantics for server-wide StarDock-mugging posture; must not weaken or overload those guards.
3. **Encounter `pvp_hard_stop`** (`fighter_toll_policy`) — live player-combat frame halt, not a sticky "this server is PvP" flag for upgrade recommend.
4. **Profile/config PvP bit** — no such field on tip.

## NO-CANON (open question for hub/Max)

**Where does `hostile_or_pvp` come from?** Candidates needing a ruling before any WIRE:

- Operator/profile declaration (`servers.toml` / world flag: peaceful vs PvP)?
- Sticky observation after a verified PvP encounter screen (and clear rules for unset)?
- Other verified non-hypothesis signal?

Until ruled, Gate #3 correctly stays fail-closed off (`False`) rather than guessing.

## Accept (close criteria)

1. STATUS cites tip SHA + grep evidence of zero writers.
2. This WO records NO-CANON; no product code change.
3. live-prove **n/a**.

## Disposition

Queue row may move READY → BLOCKED/NO-CANON (or CLOSED) per hub. Follow-on WO after ruling can implement the single chosen writer.
