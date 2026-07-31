# WO-STARDOCK-HOLD-UPGRADE-ARM

**Goal:** From Play, with StarDock known and empty cargo holds known, the
operator can confirm-to-arm a **one-pass guarded cargo-hold purchase** at
StarDock (mirror #267 trade-chain approve scaffold).

## Why (full-autonomy drive)

Early-game capital loop: explore → earn → StarDock → **buy holds** → earn
faster. Classify already names `stardock_cargo_hold_quote`; HUD tracks
empty holds; GOALS has starved `hold_price_*` vocabulary. Missing: a
default-deny arm + daemon one-pass buyer.

## Fix

1. **Plan/preview** (pure): quote summary — current empty holds, price if
   known, StarDock sector, credits if known.
2. **Play confirm** (mirror trade chain): select/offer → exact scaffold →
   Panic-abortable confirm → daemon verb.
3. **Daemon runner:** pathfind/warp to StarDock sector if not there;
   enter shipyard / cargo hold quote; buy N holds (N from plan — start
   with "buy max affordable under turn/credit rails" or explicit count);
   STOP on unknown screen / hazard / insufficient credits.
4. Default deny: no finder/FOCUS suggestion executes without confirm.

## Accept

1. Offline FakeSession / fixture path: confirm → one purchase attempt →
   honest result (ok / refused / halted).
2. Pins: incomplete scaffold never arms; Panic cancels; non-bool/hostile
   shapes refuse.
3. Does not call explore_start or trade_chain_run.
4. live-prove: hub diversity when Max sacrificial GO (money-path); else
   STATUS may say NOT-ATTEMPTED — never fake n/a.

## Scope

- New plan module + session runner + app confirm wire
- Classify/settle reuse for `stardock_cargo_hold_quote`
- tests
- `workorders/WO-STARDOCK-HOLD-UPGRADE-ARM.md`

## Constraints

- Money-path · Cipher/Mack on Accept
- Additive only; no new deps
- Never Pay fighter tolls here
- Quantity prompt handling per P-QTY research (refuse unknown ranges)

## Proof

Offline pins mandatory. Live: Max GO for turn-spend hosts.

## Refs

- #267 `WO-GUARDED-CHAIN-APPROVE-SCAFFOLD`
- `canon/research/tw2002-screen-patterns.md` P-QTY
- `.samantha/plans/full-autonomy-early-game.md`
- fixtures `stardock_cargo_hold_quote.txt`
