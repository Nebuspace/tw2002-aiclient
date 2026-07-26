# a-net letter@12 revise — false MODULE_ENTRY `T` (WO-ANET-GAME-SELECT-LETTER-STEP12)

**Tip base:** `d4bc185` latch-only (do **not** merge alone)  
**Evidence:** `/tmp/…/reprove/anet-letter-actions-191957Z/events.json`

## Live walk (hub)

C **works** → inner name → ANSI Y → **menu `Enter your choice:` send T** → show-log → pause
(“closed game”) → `game_select` again with `answered=True` → stuck.

Step6 `text_snip` is H/M/X + Exit only — **no** `T - Play` in the live menu.
`T` came from MODULE_ENTRY matching **stale scrollback**.

## Fix (a) — root

`_is_module_entry_menu(text, prompt)`:
- Require `T - Play` in the **option block attached to the current prompt**
  (`_option_block_above_prompt` — walk up; stop at blank after options).
  No magic line-count window (CC 19:24: only one fixture sample at 7 lines).
- If that block is the H/M/X access menu → **refuse**

Pins: `test_anet_hmx_access_menu_does_not_send_module_entry_t` ·
`test_module_entry_menu_still_sends_t_when_t_play_is_current`

Latch tighten from tip `d4bc185` kept.

## Residual (hub live-prove)

After false-`T` is gone, H/M/X may stagnate honestly (no taught key) — bank next door.
Closed-game pause on letter C may be host policy (SysOp gate) — not this tip’s invent.

## Out

new `screen_class` · blank-reject · README
