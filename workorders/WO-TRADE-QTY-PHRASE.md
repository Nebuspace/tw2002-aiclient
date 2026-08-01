# WO-TRADE-QTY-PHRASE

**Goal:** `trade_driver` qty prompt regex must recognize live TWGS phrasing `How many holds of <Commodity> do you want to buy|sell [N]?` (not only the short `… of <Commodity> [N]?` form).

**Live repro (hub 2026-08-01, Cartogra @ 3rdage, main `dc5ccd5`):**
- After #311 dock hotkey fix, `trade_chain_start` `2260>19662>2260` passed dock (4 sends) then halted `depleted:0:buy:Equipment`.
- Manual dock showed FO then Equipment qty prompts with full `do you want to buy` phrasing.
- Old `_QTY_PROMPT_RE` used greedy `[A-Za-z ]+?` before `[N]`, so commodity capture became `Equipment do you want to buy` ≠ hop target → never `seen_target`.

**Scope:**
- `tw2002_aiclient/trade_driver.py` — `_QTY_PROMPT_PATTERN` / `_QTY_PROMPT_RE`
- pins in `tests/test_trade_driver.py`
- both short and long phrasing must match; commodity group is Fuel Ore|Organics|Equipment only

**Accept:**
1. Pin: long buy/sell phrasing extracts commodity + qty; short form still works.
2. Suite green.
3. Live: hub proves full chain past buy Equipment (or honest halt other than depleted-from-misparse).

**Proof:** suite + hub live trade_chain.
