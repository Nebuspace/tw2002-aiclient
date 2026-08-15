# ADR Index — tw2002-aiclient

Index of every Architecture Decision Record. A decision not listed here is invisible — keep this
current whenever an ADR is added, its status changes, or it is superseded.

ADRs are append-only. Once Accepted, do not delete or silently rewrite history — update **Status**
(and thin the body when folding). If a decision changes, write a new ADR that supersedes the old one.

## Lifecycle

Status values (aligned with the sw2102-docs ADR convention; fold targets here are OKF concepts under
`canon/`, not FEATURES/SYSTEMS paths):

| Status | Meaning |
|---|---|
| **Proposed** | Open for review; not yet binding. |
| **Accepted** | Merged / ratified. The decision stands. |
| **Superseded by NNN** | A later ADR replaces this one. Keep the file; update Status only. |
| **Folded into `<concept>`** | Decision still holds; durable prose now lives in the named `canon/` concept. Thin the ADR body to context + pointer. Not a reversal. |
| **Distributed-fold: N/M** | Batch/group ADR where only *some* sub-items are verified live in tip code. `N` confirmed; `M−N` remain design-intent (flag at fold targets — never blanket-"Folded"). Graduates to plain **Folded** only when the N→M gap closes by shipping or by a tracked not-building judgment — never by re-label alone. |
| **Deprecated** | No longer applies; no replacement needed. |

**Re-verification cadence.** A **Folded** or **Distributed-fold** Index row is a claim about the
*current* tip, not a one-time stamp. Periodically re-check against code (verify-first: grep /
file:line) and append `_(re-verified YYYY-MM-DD)_` on the row. A row with no re-verify tag has not
been re-checked since it was written.

At three ADRs today this is cheap insurance — port the convention **before** the set grows past
easy retrofit size.

## Index

| # | Title | Status | Date |
|---|-------|--------|------|
| [001](001-one-tree-embedded-session.md) | One Package Tree, Embedded Session Engine | **Folded into** [session-engine](../architecture/session-engine.md) _(re-verified 2026-08-15)_ | 2026-07-24 |
| [002](002-mode-chord-ctrl-a.md) | Mode Chord Is Ctrl-A (No Printable Mode) | **Folded into** [control-and-escalation § Mode Switch](../architecture/control-and-escalation.md#the-mode-switch) _(re-verified 2026-08-15)_ | 2026-07-25 |
| [003](003-discovered-chain-approve-scaffold.md) | Discovered Chains Require Exact Approve-Scaffold Before Arm | **Folded into** [trade-loops](../strategy/trade-loops.md) _(re-verified 2026-08-15 — 8/8 gap closed)_ | 2026-07-30 |
