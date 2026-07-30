# WO-GUARDED-CHAIN-APPROVE-SCAFFOLD — Approve and run an exact discovered trade chain

**Status:** OFFLINE COMPLETE · HIGH · money-path · Max-approved 2026-07-30
**Branch:** `wo/GUARDED-CHAIN-APPROVE-SCAFFOLD`  
**Depends on:** #266 (`WO-PLAY-GATHER-CONTINUE`)

## Goal

From Play's `L)chains` modal, the operator can select one displayed discovered
profit chain, inspect an exact semantic scaffold, explicitly confirm that exact
chain, run one guarded pass, and stop it with Panic. Trade remains OFF by
default and no finder result can execute without the two-step approval/arm act.

## Scope

- **Canon lane:** `canon/ADR/003-discovered-chain-approve-scaffold.md`,
  `canon/ADR/index.md`, and the narrow promotion/run wording in
  `canon/strategy/trade-loops.md`.
- **Pure model lane:** stable chain fingerprints and semantic scaffold
  (`start anchor`, ordered sectors, ordered commodity buy/sell blocks) derived
  only from a complete `ProfitChain`; quantities remain live-bounded, never
  invented by discovery.
- **Guarded execution lane:** rebirth the archived trade-chain driver under
  `tw2002_aiclient`, preserving fresh-render, arm, abort, credit/turn floor,
  depletion, realized-loss, cargo-stranding, bounded-step, and PALADIN guards.
- **Runtime lane:** daemon-owned one-pass trade runner plus typed
  start/stop/status protocol and adapters. Start re-runs discovery and requires
  the confirmed fingerprint to match; it never substitutes another chain.
- **Cockpit lane:** discovered rows become cursor-selectable for approval while
  remaining separate from recorded macros; Enter raises the existing
  default-deny `y/N` gate and never starts directly. Live/terminal status is
  visible; Panic reaches this runner.
- **Proof lane:** pure, protocol, adapter, runner, app-wire, visual, and
  mutation pins.

These lanes are disjoint enough for a normal worker build-wave, but this
session's subagent quota is exhausted; the orchestrator is executing them
serially from this exclusive worktree under the standing lead-seat exception.

## Constraints

- Trade is OFF by default. Gather remains a no-trade data-collection behavior.
- A discovered chain is not a recorded keystroke macro. Approval authorizes
  only the exact semantic plan/fingerprint named by the gate for one pass.
- No direct finder → executor call. Enter raises intent; only `y` starts.
- The daemon re-derives the chain from current world-model data and refuses
  missing, stale, partial, truncated, below-floor, or mismatched identities.
- No guessed quantities, blind max buys, counteroffers, autonomous rotation,
  retries on unknown screens, Attack, Genesis, colonist, PvP, or destructive
  command path.
- Every send checks fresh screen + arm + abort. Disarm/Panic takes effect within
  one send-step.
- Depletion, realized loss, insufficient credits/turns, stale credits,
  stranded cargo, and any unrecognized screen STOP with a typed reason.
- One confirmed launch runs one pass only. Repeating runs require another
  explicit confirm in a later work order.
- No external dependency, schema migration, shared runtime deploy, or live
  turn/credit spend without Max's separate sacrificial GO.
- Keep product Python modules below the repository's 1,500-line ceiling.

## Accept

- [x] `L)chains` distinguishes recorded macros from discovered chains and can
      cursor-select discovered rows without merging them into the macro store.
- [x] Enter on a discovered row performs zero sends and raises a gate naming
      the exact route, commodities, hop count, one-pass bound, cash floor, and
      turn reserve; any unknown field refuses to arm.
- [x] `N`, Esc, malformed input, stale fingerprint, truncated discovery, or
      discovery failure creates no runner and issues zero sends.
- [x] `y` starts exactly the confirmed chain; daemon re-resolution cannot
      substitute the current best or another same-sector cycle.
- [x] Start anchor mismatch refuses before the first send.
- [x] Quantity/offer cascades preserve archived guards and only permit `P`,
      `T`, sector digits, bounded quantities, `0` declines, and blank standing
      offer acceptance. `A` is structurally unreachable.
- [x] Panic stops Explore, recorded autoloop, and guarded trade; the trade
      runner observes stop/disarm within one send-step.
- [x] Status/progress names `trade`, route, hop progress, and terminal STOP
      reason without claiming success when credits/cargo reconciliation fails.
- [x] Full offline suite passes.
- [x] Static safety/mutation pins pass for arm, abort, stale identity, floors,
      depletion, unexpected screens, and PALADIN.

## Proof

```bash
pytest -q -n 0 tests/test_trade_chain_plan.py tests/test_trade_driver.py \
  tests/test_trade_chain_protocol.py tests/test_trade_chain_runner.py \
  tests/test_play_chains_discovered.py tests/test_play_panic_wire.py \
  tests/test_cockpit_panic.py
pytest -q -m "not live_login and not pty_ui"
```

Observed 2026-07-30: corrected serial acceptance set **105 passed**; full
offline suite **passed**. The first full pass also exercised the structural
arm-callsite, control-lock-callsite, never-auto-action inventory,
import-hygiene, and bounded-global-status guards; all are green after review.

Live proof is **NOT-ATTEMPTED** until the offline money-path review is accepted.
After that, Cursor may run safe transport/attach probes. A one-pass
credit/turn-spending arm still requires Max's explicit sacrificial GO.

## Refs

- `canon/strategy/trade-loops.md`
- `canon/architecture/app-autopilot-model.md`
- `canon/engine/screen-understanding.md` § money-prompt guarded-rule exemption
- `workorders/WO-DISCOVERED-TO-TAUGHT-PROMOTION.md` (superseded design blocker)
- `.samantha/plans/proposition-discovered-to-taught-20260728.md` (B2)
- `.samantha/plans/gather-continue-and-guarded-chain-trade-2026-07-30.md`
- archived `f583ad9:twclient/trade_driver.py`
