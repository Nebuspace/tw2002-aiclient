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

**Distributed-fold: 6/8** · Accepted 2026-07-30 by Max (`Continue; your choice` after the
B1/B2 choice; Samantha selected recommended B2 approve-scaffold) ·
_(re-verified 2026-08-06)_

Durable prose lives primarily in [`trade-loops.md`](/strategy/trade-loops.md)
(Discovered → approved semantic plan · tip `trade_chain_plan.py`). This ADR remains
the decision record / pointer.

**Confirmed on tip (6):**
1. Exact-fingerprint approve-scaffold (`trade_chain_plan.plan_from_chain` / preview)
2. Separate default-deny confirm gate (`begin_arm_confirm` · arm ≠ Enter alone)
3. Daemon start re-derive + refuse on missing/partial/stale fingerprint
4. One-pass authority (repeat needs another confirm)
5. Partial-discovery display honesty (`chain_search_view.py` · `PARTIAL_*` banner;
   empty+truncated ≠ bare "no profit chains") — re-verified tip module present
6. Guarded tip `trade_driver.run_chain` under arm/abort/floor rails (divergence
   closed in trade-loops ADR-003 section)

**Still design-intent / process (2 — do not blanket-Fold):**
7. Sacrificial live-prove gate for turn/credit-spending proof (hub/Max process,
   not a missing tip module) — tracked as an open residual item in
   `workorders/WO-CANON-ROLLUP-ADR-003-DISTRIBUTED-FOLD-TAG.md` (Accept #2);
   no dedicated hub/Max-process WO beyond that pointer exists yet.
8. Bounded-repeat contract (explicitly future; one-pass until separately reviewed) —
   same tracking: `workorders/WO-CANON-ROLLUP-ADR-003-DISTRIBUTED-FOLD-TAG.md`
   (Accept #2) names it a residual alongside item 7; no separate design/build WO
   exists yet — untracked beyond this pointer, needs one when the bounded-repeat
   review is actually scoped.

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
- The first version is one pass. Repeating the chain requires another explicit
  confirm until a separately reviewed bounded-repeat contract exists.
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
- tip: `tw2002_aiclient/chain_search_view.py` · `cockpit/chains.py`
