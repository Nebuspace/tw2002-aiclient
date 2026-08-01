# WO-TRADE-DOCK-MENU

**Goal:** `trade_driver._dock` must survive live TWGS port entry where the post-`P` prompt is not the classic port-menu line, and/or commerce opens commodity prompts in FO→Org→Equ order before the hop’s target commodity — decline non-targets with `0` until the hop commodity (or honest halt).

**Live repro (hub 2026-08-01, Cartogra @ 3rdagetwgs, main `2816731`):**
- Uncontested `trade_chain_start` route `2260>19662>2260` (Equipment→Organics), empty holds, `subs=0`.
- Start ok; first hop sent `P`; run halted `unexpected_screen:dock_menu:0` (`hops_completed=0`, `sends_issued=1`, `credits_delta=0`).
- Screen showed commerce report + `How many holds of Fuel Ore do you want to buy` / offer — FO offered before Equipment.
- Manual P/T commerce on same server works; gather explore+dock refreshes stale (>1h) commodity ages (`DEFAULT_MAX_AGE_S`).

**Scope:**
- `tw2002_aiclient/trade_driver.py` — `_dock` / visit-port cascade
- pins under `tests/` (fixture screens: post-P commerce without menu line; FO-then-Equipment skip with `0`)
- do not change explore gather semantics

**Accept:**
1. Live-shaped fixture: after `P`, if commerce qty/offer prompts appear for a non-hop commodity → send `0` (and accept/decline offers per existing safe rules) until hop commodity or exhausted cascade → continue hop; do not `ChainHold(dock_menu)` solely because port-menu regex missed.
2. If post-`P` is still a recognizable port menu → existing `T` path unchanged.
3. Pins green; full suite green.
4. Live: NOT-ATTEMPTED OK if offline Accept met (hub repro stands).

**Proof:** suite + pins. No self-merge.
