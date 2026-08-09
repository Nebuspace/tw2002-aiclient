---
type: ADR
title: ADR 003 — Discovered Chains Require Exact Approve-Scaffold Before Arm
description: A discovered ProfitChain may become a one-pass guarded trade behavior only through an exact human-approved semantic scaffold and a separate confirm gate.
tags: [adr, trade, profit-chain, approval, arm-confirm, money-path]
timestamp: 2026-07-30T22:01:00Z
---

# ADR 003 — Discovered Chains Require Exact Approve-Scaffold Before Arm

---

## Status

**Folded into** [`trade-loops.md`](/strategy/trade-loops.md) · Accepted 2026-07-30 by Max
(`Continue; your choice` after the B1/B2 choice; Samantha selected recommended B2
approve-scaffold) · _(re-verified 2026-08-09 — N→M gap closed)_

Durable prose lives primarily in trade-loops (Discovered → approved semantic plan · tip
`trade_chain_plan.py`). This ADR remains the decision record / pointer.

**Confirmed on tip (8/8 — gap closed by shipping + tracked process judgment):**
1. Exact-fingerprint approve-scaffold (`trade_chain_plan.plan_from_chain` / preview)
2. Separate default-deny confirm gate (`begin_arm_confirm` · arm ≠ Enter alone)
3. Daemon start re-derive + refuse on missing/partial/stale fingerprint
4. One-pass authority by default (a single arm is still one pass unless bounded-repeat
   is explicitly requested)
5. Partial-discovery display honesty (`chain_search_view.py` · `PARTIAL_*` banner;
   empty+truncated ≠ bare "no profit chains") — re-verified tip module present
6. Guarded tip `trade_driver.run_chain` under arm/abort/floor rails (divergence
   closed in trade-loops ADR-003 section)
7. Sacrificial live-prove gate for turn/credit-spending proof — **ruled non-blocking,
   2026-08-09** (`workorders/WO-ADR-003-RESIDUAL-7-8-TRACKING.md`): standing Nebuspace
   merge-ritual live-prove process, concretely exercised by
   `WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE` (DONE — `scout_academy`, 6 instrumented cycles).
   Tracked not-building judgment (process exists; nothing further to build in tip).
8. Bounded-repeat contract — **shipped 2026-08-09** via
   `WO-BUILD-BOUNDED-REPEAT-TRADE-CHAIN-DRIVER` (PR #637 · tip module
   `tw2002_aiclient/bounded_repeat_trade_chain_driver.py`; Max GO sacrificial-only;
   defense-in-depth `pass_count` + per-re-arm X5 floor + `profit_target`; CLI
   `--pass-count` / `--profit-target`). Supersedes the earlier GATED design-brief row
   `WO-CANON-DRAFT-BOUNDED-REPEAT-CONTRACT-SCOPE`. Default remains one-pass; multi-pass
   is explicit and sacrificial-gated.

---

## Context

The chain finder produces profitable cycle suggestions from gathered port data,
while the existing launcher arms only recorded keystroke macros. A discovered
`ProfitChain` has sectors, commodity hops, margins, and turn estimates but no
human-taught quantities or safe authority to spend credits. Keeping discovered
chains permanently display-only made the cockpit honest but prevented the
requested explicit Trade mode; wiring the finder directly to execution would
violate the human-arm and never-unattended-money contracts.

---

## Decision

A discovered chain remains non-executable until the operator selects its exact
fingerprint, reviews a deterministic semantic scaffold (start anchor, ordered
route, and commodity buy/sell blocks with quantities explicitly unresolved),
and accepts it; that approval creates authority for only that exact one-pass
plan, after which a separate default-deny confirm arms it. At start the daemon
re-derives discovery and refuses any missing, partial, truncated, stale, or
mismatched fingerprint; quantities are computed and bounded from fresh live
screens, every send re-validates guards, and direct finder-to-executor launch or
automatic substitution/rotation remains forbidden.

---

## Consequences

- The two visible populations stay distinct: recorded macros remain recorded
  macros; discovered chains gain a deliberate approval path, not silent
  membership in the macro store.
- The displayed chain becomes useful without pretending discovery supplied
  exact transaction quantities.
- Approval and arm are two acts. Enter alone spends nothing; cancellation,
  drift, or missing evidence fails closed.
- Default authority is still one pass (another explicit confirm for another arm).
  Bounded multi-pass is available only via the sacrificial-gated
  `bounded_repeat_trade_chain_driver` (explicit `pass_count` / `profit_target`), not as
  silent default re-arm.
- Runtime work must rebirth the archived guarded trade driver under the current
  daemon run-loop, preserving its arm, abort, floor, depletion, reconciliation,
  and PALADIN rails.
- Live proof that spends turns or credits remains a separate sacrificial gate.
- **Display honesty for partial discovery** lives in tip
  `tw2002_aiclient/chain_search_view.py` (pure formatter; no arm/send path). The
  `L)chains` modal's discovered section is composed here via
  `cockpit/chains.compose_chain_lines` — dependency points *into* the formatter,
  never the reverse. Truncation is part of the rendering, not a footnote:
  any truncated search prepends a `PARTIAL_*` banner; an empty *and* truncated
  result says *"none found in the part searched (not exhaustive)"*, never a bare
  *"no profit chains"* (absence was not established). Blurring this listing with
  `cockpit/chains.py`'s recorded-macro ARM `rows` (money path) is a safety defect.
  (`AUDIT-CANON-DRAFT-CHAINSEARCH-HONESTY-CONTRACT`, 2026-08-04.)

---

## Refs

- Max delegated B1/B2 choice, 2026-07-30
- `canon/strategy/trade-loops.md`
- `canon/architecture/app-autopilot-model.md`
- `workorders/WO-GUARDED-CHAIN-APPROVE-SCAFFOLD.md`
- `workorders/WO-ADR-003-RESIDUAL-7-8-TRACKING.md` (items 7 & 8 disposition, 2026-08-09)
- tip: `tw2002_aiclient/chain_search_view.py` · `cockpit/chains.py`
