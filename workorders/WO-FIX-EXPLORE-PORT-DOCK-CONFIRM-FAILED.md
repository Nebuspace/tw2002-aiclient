# WO-FIX-EXPLORE-PORT-DOCK-CONFIRM-FAILED

**Goal:** Dock-new-ports must not halt `confirm_failed` on a real commerce
qty screen (joes_tavern Fuel Ore) due to mid-paint settle races / ANSI in
the prompt row.

**Fix:**
- `retry_unstable_idle=True` on dock letter sends (P/T) and gather `0` declines
- Strip SGR from prompt before quantity/menu marker matches

## Accept

1. Live-shaped ANSI qty prompt matches after `_plain_prompt`.
2. `_send_dock_letter` retries unstable idle (same family as warp/trade nav).

## Refs

queue-aiclient.md · `scout_joes` / `session-20260807T230607Z.log`
