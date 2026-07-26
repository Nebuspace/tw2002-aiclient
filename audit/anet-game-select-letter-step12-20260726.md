# a-net letter@12 revise — false MODULE_ENTRY `T` (WO-ANET-GAME-SELECT-LETTER-STEP12)

**Tip base:** `d4bc185` latch-only (do **not** merge alone)  
**Evidence:** `/tmp/…/reprove/anet-letter-actions-191957Z/events.json` · hub 194056Z module-entry note

## Live walk (hub)

C **works** → inner name → ANSI Y → **menu `Enter your choice:` send T** → show-log → pause
(“closed game”) → `game_select` again with `answered=True` → stuck.

Step6 `text_snip` is H/M/X + Exit only — **no** `T - Play` in the live menu.
`T` came from MODULE_ENTRY matching **stale scrollback**.

## Fix (a) — root

`_is_module_entry_menu(text, prompt)`:
- Require `T - Play` in the **option block attached to the current prompt**
  (`_option_block_above_prompt` — walk up; stop at blank after options).
  No magic line-count (CC 19:24).
- **Do not** refuse on H/M/X presence alone — live a-net module-entry can
  list T/I/S *and* H/M/X in the **same** block (hub 194056Z); blank separator
  is what excludes stale scrollback.

Pins: `test_anet_hmx_access_menu_does_not_send_module_entry_t` ·
`test_module_entry_menu_still_sends_t_when_t_play_is_current`

Latch tighten from tip `d4bc185` kept; `_left_game_select_for_real` forwards
`prompt` into the option-block helper.

## Residual (hub live-prove)

After false-`T` is gone, H/M/X may stagnate honestly (no taught key) — bank next door.
Closed-game pause on letter C may be host policy (SysOp gate) — not this tip’s invent.
If failure relocates again → whole-walk capture (CC tripwire).

## Out

new `screen_class` · blank-reject · README

## Hub live 2026-07-26T19:46Z (tip 4f9647b)

Letter C + MODULE_ENTRY T path works. Host then prints closed-game refusal
("You must request a player account…") and returns to TWGS door. Fail-loud
`game_closed` added so door re-entry cannot loop. Matrix: a-net letter C =
honest FAIL (policy), not automaton stuck.
