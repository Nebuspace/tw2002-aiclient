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
approve-scaffold) · _(re-verified 2026-08-15 — 8/8 gap closed)_

Durable prose lives primarily in trade-loops (Discovered → approved semantic plan · tip
`trade_chain_plan.py`). This ADR remains the decision record / pointer. The former
itemized tip checklist was historical once the Distributed-fold N→M gap closed
(shipping + tracked not-building judgments) and has been removed
(`WO-CANON-ROLLUP-ADR-003-THIN-BODY`); see Refs for residual disposition WOs.

---

## Context

The chain finder produces profitable cycle suggestions from gathered port data,
while the launcher arms only recorded keystroke macros. A discovered `ProfitChain`
has route/margin estimates but no human-taught quantities or safe authority to
spend credits. Display-only discovery was honest but blocked an explicit Trade
mode; wiring the finder straight to execution would violate human-arm and
never-unattended-money.

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

- Recorded macros and discovered chains stay distinct populations; discovery
  never silently joins the macro store.
- Approval and arm are two acts (Enter alone spends nothing). Default authority
  is one pass; bounded multi-pass is explicit and sacrificial-gated
  (`bounded_repeat_trade_chain_driver`).
- Partial-discovery display honesty and guarded `trade_driver.run_chain` rails
  live in tip modules cited from trade-loops — not re-litigated here.
- Live proof that spends turns or credits remains a separate sacrificial gate.

---

## Refs

- Max delegated B1/B2 choice, 2026-07-30
- `canon/strategy/trade-loops.md`
- `canon/architecture/app-autopilot-model.md`
- `workorders/WO-GUARDED-CHAIN-APPROVE-SCAFFOLD.md`
- `workorders/WO-ADR-003-RESIDUAL-7-8-TRACKING.md` (items 7 & 8 disposition, 2026-08-09)
- `workorders/WO-CANON-ROLLUP-ADR-003-THIN-BODY.md` (Status checklist trim)
- tip: `tw2002_aiclient/trade_chain_plan.py` · `chain_search_view.py` · `cockpit/chains.py`
  · `bounded_repeat_trade_chain_driver.py`
