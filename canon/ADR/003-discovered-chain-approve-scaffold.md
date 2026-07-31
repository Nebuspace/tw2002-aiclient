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

Accepted · Accepted 2026-07-30 by Max (`Continue; your choice` after the
B1/B2 choice; Samantha selected recommended B2 approve-scaffold)

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

---

## Refs

- Max delegated B1/B2 choice, 2026-07-30
- `canon/strategy/trade-loops.md`
- `canon/architecture/app-autopilot-model.md`
- `workorders/WO-GUARDED-CHAIN-APPROVE-SCAFFOLD.md`
