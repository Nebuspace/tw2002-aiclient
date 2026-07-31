# WO-PRIORITY-ENGINE-FOCUS-WIRE

**Goal:** Produce a live `status["focus"]["candidates"]` payload so the
FOCUS panel stops rendering empty and ranks the early-game effort
choices: trade chain · explore · hold upgrade (when evidence exists).

## Why (full-autonomy drive)

`cockpit/focus.py` is a starved consumer — it only displays engine order.
Without a producer, FOCUS stays blank and the operator/policy loop has
no ranked next action. Canon: FOCUS never auto-sends; it only suggests.

## Fix

Smallest producer (new module or `world_stats` / `chain_status` companion):

1. Build candidates from evidence already on tip:
   - `run_chain` — if ≥1 priced executable ProfitChain (use
     `is_executable_chain`); `ev_per_turn` from best local-prefer chain
     when sector known, else global best.
   - `explore` — if map incomplete / no executable chain yet /
     StarDock unknown (honest gates).
   - `upgrade` — if StarDock known **and** empty cargo holds known **and**
     (optional) hold price known; else `gated=True` with reason.
2. Sort by ungated EV desc; gated last (or engine rule from
   `canon/engine/priority-engine.md` — tip-check and follow).
3. Attach via existing status merge wrap (same pattern as
   `ChainScalars.merge` / `WorldStats.merge`) so Play draw sees
   `status["focus"]`.
4. No sends. No arm. No ranking inside `focus.py`.

## Accept

1. Unit: with synthetic chains + sector → `focus.candidates` nonempty;
   top ungated `run_chain` when executable chain exists.
2. Unit: no chains / incomplete map → `explore` candidate present.
3. Unit: StarDock unknown → `upgrade` gated with reason (or omitted —
   pick one and pin).
4. `compose_focus_lines` renders non-empty on merged status.
5. pytest pins green.

## Scope

- New or existing producer module under `tw2002_aiclient/`
- Status merge wrap call site (`app.py` / play provider)
- `tests/` pins
- `workorders/WO-PRIORITY-ENGINE-FOCUS-WIRE.md`

## Out of bounds

- Auto-arm / auto-send of any candidate
- Changing FOCUS composer ranking
- Cargo purchase execution (separate WO-STARDOCK-HOLD-UPGRADE-ARM)

## Proof

Offline pins. live-prove **n/a** (status payload; no live arm).

## Refs

- `canon/engine/priority-engine.md` · `cockpit/focus.py`
- `.samantha/plans/full-autonomy-early-game.md`
- #267 guarded chain · #250 StarDock GOALS · #273/#275 local chain
