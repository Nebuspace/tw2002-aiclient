# WO-ADAPTERS-FIGHT-TOLLS — Forward fight_tolls through adapters (Play path)

**Status:** OPEN · EXECUTE · HIGH · automation morning bar
**Posted:** 2026-07-29T03:02Z · Max: meaningful client automation by morning
**Seat:** Claude Code (impl-claudecode-aiclient) after #209 MERGED
**Depends:** #209 / wo/FIGHTER-TOLL-POLICY-WIRE on main (CLI+daemon already have the flag)
**Refs:** adapters.explore_start dock_new_ports mirror · Max combat GO · cockpit UX still banked

## Why

#209 lands CLI/daemon --fight-tolls, but adapters.explore_start / explore_start_for_profile only forward dock_new_ports. Play and any adapter caller cannot arm the toll policy — automation stays CLI-only. This WO closes that hole without inventing a full cockpit confirm UI (still banked).

## Goal

Any product caller of adapters.explore_start* can pass fight_tolls: bool the same way as dock_new_ports (omit when None; refuse non-bool at daemon).

## Accept

1. adapters.explore_start + explore_start_for_profile accept optional fight_tolls: bool | None = None; when not None, payload includes bool (mirror dock).
2. Pin: adapter forwards exact bool; mutation omitting forward goes red.
3. No Play curses invent; no default-ON; library/CLI defaults stay False.
4. Suite green · live n/a with reason (adapter wire; live covered by #209) unless hub asks a smoke.
5. STATUS + PR.

## Constraints

Safety-list adjacent. Never send Pay. No widen Option?. Public-safe. Do not flip dock default.
