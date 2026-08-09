# WO-ADR-003-RESIDUAL-7-8-TRACKING — Closing the N/M gap for items 7 & 8

**Status:** DONE (docs/process only — no product behavior) · **item 8 follow-through:**
shipped same day via `WO-BUILD-BOUNDED-REPEAT-TRADE-CHAIN-DRIVER` (PR #637); ADR-003
graduated to Folded (see tip-true pass `workorders/WO-CANON-FIX-ADR-003-ITEM8-TIP-TRUE.md`).
**Answers:** `WO-CANON-ROLLUP-ADR-003-RESIDUAL-ITEMS-7-8-TRACKING-WO` / queue
`WO-CLEANUP-ADR-003-RESIDUAL-ITEMS-7-8-TRACKING-WO` (queue-aiclient.md)

## Goal

ADR-003's index row reads **Distributed-fold: 6/8**. Per the ADR index's own lifecycle
rule (`canon/ADR/index.md` § Lifecycle), a Distributed-fold status "graduates to plain
Folded only when the N→M gap closes by shipping or by a tracked not-building
judgment — never by re-label alone." Items 7 and 8 each had a single one-line pointer
(to `workorders/WO-CANON-ROLLUP-ADR-003-DISTRIBUTED-FOLD-TAG.md` Accept #2) but no real
disposition. This WO gives each item an actual ruling, verified against current tip and
current queue state — not a re-label.

## Verify-first findings

**Item 7 — sacrificial live-prove gate for turn/credit-spending proof.**

The ADR's own text already frames this as *"hub/Max process, not a missing tip
module."* That process is not ADR-003-specific — it is the standing Nebuspace
merge-ritual gate (`.cursor/rules/workorders-required.mdc` § Hub merge ritual step 1,
`.cursor/rules/live-prove-pushback.mdc`): every product/money-path PR gets a live-prove
pass before Accept. It was never going to "ship" as a tip code module, because it isn't
one.

More importantly, that process has now been **concretely exercised against this exact
ADR-003 discovered-chain flow**: `WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE` (queue-aiclient.md,
HIGH, **✅DONE** — live-proven 2026-08-09 on the `scout_academy` sacrificial profile,
`crawl_sacrificial=true`) ran 6 instrumented live cycles of the discovered-chain
approve→confirm→arm→run path, spending real turns and credits
(Δ 1790/1781/1821/1773/1779/1771cr per cycle). It refuted single-arm doubling and
confirmed profitable linear per-cycle growth — i.e. it *is* a completed sacrificial
live-prove pass over ADR-003's guarded-chain-execution consequence ("Live proof that
spends turns or credits remains a separate sacrificial gate").

**Ruling:** item 7 does **not** block ADR-003 graduating past Distributed-fold. It is a
recurring hub/Max process (already standing, already documented outside this ADR) that
has already been instantiated once against this exact flow. There is nothing further for
a code WO to build. Closed as **shipped** (process exists + concretely exercised), not
as a design punt.

**Item 8 — bounded-repeat contract.**

Genuinely unresolved. `WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE`'s own STATUS names it
explicitly as the blocker to real automated doubling: *"One arm = one 2-hop cycle then
STOP (ADR-003 one-pass by design) — real 2x needs ~57 re-arms, not a single-arm event.
`tw chain start` CLI doesn't expose protocol's `profit_target`; unattended multi-cycle
chaining is the still-GATED bounded-repeat primitive."*

This is already tracked with mailing-address precision as its own queue row:

- **`Nebuspace/.samantha/coord/queue-aiclient.md`: `WO-CANON-DRAFT-BOUNDED-REPEAT-CONTRACT-SCOPE`**
  — MED, **GATED (human)**, `vs 2f76d72 (ADR-003:33-42) [2 finders]` — *"ADR-003 item 8
  loop-repeat primitive never scoped (pass-count? floor re-check? value ceiling?). Design
  brief."*
- Follow-on execute row also present:
  **`Nebuspace/.samantha/coord/queue-aiclient.md`: `WO-BUILD-DEV-DRIVE-CLI-SURFACE`**
  — HIGH, GATED (human) — needed before any bounded-repeat CLI surface (`tw chain start`
  doesn't expose `profit_target` today) can be built.

**Ruling:** item 8 stays an open, tracked, human-gated design item — the lifecycle
rule's "tracked not-building judgment" escape hatch, not a re-label. It is **not**
untracked (contra the ADR's current "no separate design/build WO exists yet" text) — it
already has a real GATED queue row with a rationale and a named follow-on. ADR-003
cannot graduate to plain Folded while this item is open; that is correct, not a gap in
this WO.

## Scope

- `workorders/WO-ADR-003-RESIDUAL-7-8-TRACKING.md` (this file)
- `canon/ADR/003-discovered-chain-approve-scaffold.md` (Status section, items 7 & 8 only)
- `canon/DECISIONS.md` (one new tracking entry)

**Out of scope (original pass):** no product code changed. *Follow-through (same day):*
item 8 shipped via `WO-BUILD-BOUNDED-REPEAT-TRADE-CHAIN-DRIVER` (PR #637); ADR-003
graduated to Folded — see `workorders/WO-CANON-FIX-ADR-003-ITEM8-TIP-TRUE.md`.

## Accept

1. ADR-003 item 7 states the ruling above (process, already exercised, does not block
   Folded) with a citation to `WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE`.
2. ADR-003 item 8 states the ruling above (open, human-gated, tracked) with
   mailing-address-precise citations to the two queue-aiclient.md rows.
3. `canon/DECISIONS.md` carries a short Accepted/Pending entry linking both items to
   their tracking WOs so a future re-verify pass does not rediscover this from scratch.
4. ADR-003 Status remained **Distributed-fold: 6/8** at this WO's Accept time (item 8
   still open then). Superseded same-day by tip-true Folded graduation after #637.
5. `chain_search_view.py` addendum spot-checked against tip (still a pure formatter, no
   arm/session/curses import) — no rewrite needed.

## Proof

Docs-only change; no runtime behavior touched. `live-prove: n/a` (docs/process). Grep
verification of citations:
`grep -n "WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE\|WO-CANON-DRAFT-BOUNDED-REPEAT-CONTRACT-SCOPE" ../../.samantha/coord/queue-aiclient.md`
(run against the Nebuspace coord tree at authoring time — both rows present and in the
states quoted above).

## Refs

- `canon/ADR/003-discovered-chain-approve-scaffold.md`
- `canon/ADR/index.md` § Lifecycle (Distributed-fold graduation rule)
- `workorders/WO-CANON-ROLLUP-ADR-003-DISTRIBUTED-FOLD-TAG.md`
- `Nebuspace/.samantha/coord/queue-aiclient.md`: `WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE`,
  `WO-CANON-DRAFT-BOUNDED-REPEAT-CONTRACT-SCOPE`, `WO-BUILD-DEV-DRIVE-CLI-SURFACE`
