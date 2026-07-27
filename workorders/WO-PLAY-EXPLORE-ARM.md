# WO-PLAY-EXPLORE-ARM

**Status:** DONE · CC · adapter mocked pending L2 · **depends on** adapter contract in `WO-PLAY-EXPLORE-ADAPTER` (mock until merged)  
**Posted:** 2026-07-27T03:10:33Z · One-client Play ladder **L3**  
**Seat:** impl-claudecode-aiclient (product wire · first live arm path)  
**Plan:** `.samantha/plans/one-client-play-ladder-20260727.md`

## Goal

Make explore reachable **inside Play** with one deliberate confirm — no CLI.

After `_run_play` ensure succeeds at `main_command`, raise the existing confirm-to-arm gate; on `y`, start explore via `adapters.explore_start_for_profile` (or `explore_start` + derived world_id).

## Why

`begin_arm_confirm` exists; **zero** production callers. Max cannot see automation from chrome that never arms. This is the first money-path confirm that actually starts a taught strategic behavior (frontier explore), still human-gated (`y/N`).

## Scope (owned)

- `tw2002_aiclient/app.py` — after successful ensure @ `main_command` (or equivalent ready classification), call `play.begin_arm_confirm(action="Explore", cycles=5)` (wording via existing `compose_arm_confirm_line`); handle returned `"arm_confirm"` → `adapters.explore_start_for_profile(profile, min_sectors=5)`; set `status_line` from result
- `tw2002_aiclient/screens.py` — only if needed to allow the gate raise / intent (prefer app.py-only)
- Tests: extend play/pty or armconfirm suite — **must flip** the pin that “no production call site invokes `begin_arm_confirm`” (that pin becomes “exactly one production path: post-ensure explore offer”)

## Out of scope

- Binding teach `T` / `A` / `R` (WO-067/068/069 own those)
- Autopilot `game_select` / changing Autopilot halt behavior
- L4 live sector tick HUD (status_line one-shot “explore started / failed” is enough here)
- New deps / daemon protocol changes

## Constraints

- Confirm gate stays default-deny (`y` only arms) — do not weaken
- `no_auto_arm=True` on ensure stays — explore is a **separate** human confirm, not silent auto-arm of Autopilot
- If ensure did **not** land `main_command`, do **not** raise the explore offer (status_line already shows failure/halt)
- If L2 not on tip yet: stub/`unittest.mock` the adapter in tests; land product code against the pinned contract; do not reimplement `send_request` in app.py

## Accept

1. Ensure OK + `main_command` → confirm line visible (danger+reverse path already in armconfirm)
2. `y` → explore_start invoked once with `min_sectors=5` (mocked in unit/pty test)
3. Non-`y` → gate clears, explore **not** started
4. Ensure fail / non-main classification → no explore offer
5. The old “no production begin_arm_confirm caller” pin is updated to assert the post-ensure path (not deleted into silence)
6. Targeted pytest green (`test_cockpit_armconfirm` + new/extended play-path test)

## Proof

```text
pytest tests/test_cockpit_armconfirm.py tests/<new_or_extended_play_explore_arm>.py -q -n0
```

Hub live secondary (after L2 on main): Play on micro → see confirm → `y` → explore runs (pair with L4 for sector tick visibility).

## Refs

- `screens.py` `begin_arm_confirm` / `handle_key` arm_confirm branch
- `cockpit/armconfirm.py`
- `app.py` `_run_play`
- `workorders/WO-PLAY-EXPLORE-ADAPTER.md`
- `canon/architecture/north-star.md` · `canon/strategy/exploration-policy.md`
