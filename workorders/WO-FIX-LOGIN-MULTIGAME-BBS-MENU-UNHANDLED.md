# WO-FIX-LOGIN-MULTIGAME-BBS-MENU-UNHANDLED

**Goal:** When TWGS multi-game door classifies as `menu` (no "Select a
game" cue), send `profile.game_letter` if `<L>` appears on the live menu —
ending `automaton_stuck:menu` with a correct letter (moon_base_alpha `T`).

**Fix:** `_menu_offers_game_letter`; expand `menu` decide branch; single-key
menu sends use `enter=False` + same `game_select_letter_sent` latch.

## Accept

1. Menu offering `<T>` + `game_letter=T` → send `T`.
2. Letter not on menu → no send (still fail-loud).
3. Unit pins against moonbase-shaped fixture.

## Refs

queue-aiclient.md · `scout_moonbase` / `session-20260807T230828Z.log`
