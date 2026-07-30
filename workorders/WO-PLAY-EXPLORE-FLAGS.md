# WO-PLAY-EXPLORE-FLAGS — Opt-in dock + fight_tolls from Play explore arm

**Status:** DONE · origin `8cfda01` (#212) · Accept verified 2026-07-30
**Posted:** 2026-07-29T04:46Z · Max carte blanche / automation continuity
**Seat:** impl-claudecode-aiclient (offline) · live → Cursor
**Depends:** #211 on main `f8400e8` (adapters forward both flags; dock path option-3 safe)
**Refs:** `app.py` explore arm (~1116) · `adapters.explore_start_for_profile` · WO-EXPLORE-DOCK-DEFAULT-OFF · WO-ADAPTERS-FIGHT-TOLLS

## Why

Morning bar landed Survive / Armable / Gather on **CLI + adapters**. Play still arms explore with **neither** flag — comment at the call site says "Opt-in later via an explicit Play control." Operators cannot see dock commodities or toll survival from the cockpit without leaving Play for CLI. Visible automation = reachable from Play.

## Goal

Give Play an **explicit, default-OFF** way to pass `dock_new_ports` and/or `fight_tolls` into `adapters.explore_start_for_profile` when the operator confirms Explore.

## Accept

1. Library / Play defaults remain **False** for both flags (no silent ON).
2. Operator can opt in to each flag via an explicit Play control **before** or **as part of** the existing explore confirm gate — not a silent side effect of `y`.
3. When opted in, `explore_start_for_profile` is called with the corresponding kwarg(s); when not, kwargs omitted or False (daemon stays off).
4. Pins: default path unchanged; opt-in path forwards exact bools; non-`y` clears without starting; mutation reddens a dropped forward.
5. No Play curses invent for a full settings panel — smallest control that is operator-visible (status/confirm chrome OK).
6. Suite green · STATUS · **Live: DEFERRED → Cursor** (hub will HANDOFF live after tip).

## Constraints

- Do **not** flip CLI/library defaults ON.
- Do **not** implement option-2 (`0` decline) or auto-trade.
- Do **not** claim `Your offer` as `money_prompt` (canon collision with auto-haggle — banked separately).
- Fighter halt-reason rename (`unrecognized_screen` vs `fighter_encounter`) is **out of scope** — banked follow-on.
- Public-safe only.

## Proof

```text
pytest tests/test_cockpit_armconfirm.py tests/test_adapters_explore.py tests/<new_or_extended> -q -n0
# + suite on PR
```
