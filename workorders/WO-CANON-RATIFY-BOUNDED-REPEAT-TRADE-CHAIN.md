# WO-CANON-RATIFY-BOUNDED-REPEAT-TRADE-CHAIN

**Status:** OPEN on PR #674 (`wo/CANON-RATIFY-BOUNDED-REPEAT-TRADE-CHAIN`) — docs landed; awaiting hub verify + merge.

**Goal:** Close WO-ESCALATE-BOUNDED-REPEAT-TRADE-CHAIN-UNDOCUMENTED-AUTOMATION per Max's direct ruling (relayed via orchestrator, 2026-08-10): **Ratify as intentional.** This matches his prior carte-blanche for tw2002 autonomous trade+chain-seeking on disposable/sacrificial accounts (2026-07-21 witness carte-blanche).

**Scope:** `canon/strategy/trade-loops.md`, `canon/DECISIONS.md`, and (if warranted) a new/amended ADR — implementer's call on ADR vs DECISIONS-only given `bounded_repeat_trade_chain_driver.py`'s actual shape. Also, per the 2026-08-10T19:18:00Z scope amendment (cycle-52 audit independently re-found the same gap with more scope than originally named):
- `canon/architecture/app-autopilot-model.md` — its Code Divergences section still says the TradeChainRunner "executes one pass" / "no replacement-chain rotation exists," unqualified. Add the sacrificial-only bounded-repeat qualifier here too, not just trade-loops.md.
- `canon/architecture/cli-verbs.md` — zero mention of the `tw chain start --pass-count`/`--profit-target` flags that exist in `session/cli.py`. Add an entry.
- `canon/testing/test-case-catalog.md` — silent on `tests/test_bounded_repeat_trade_chain_driver.py` (228 lines, on main). Add an entry.

**Constraints:** the ruling ratifies the mechanism AS SHIPPED — `is_crawl_sacrificial`-only gating, `DEFAULT_MAX_PASSES=10` / `PASSES_HARD_CEILING=50`, stop-loss floor + profit-target re-check before every re-arm (first trip wins). Default behavior remains one-pass. Do not silently widen scope (e.g. don't extend to non-sacrificial profiles) — that would be a new design question, not this ruling.

**Accept:**
1. `canon/DECISIONS.md` gets a new entry (mirror existing format, e.g. `DECISION-PORT-FLOOR-CAPTURE-HOLD-RATIONALE`'s style) documenting: the ruling, the exact caps/gating above, and citing this as the origin (Max ruling via orchestrator, 2026-08-10).
2. `canon/strategy/trade-loops.md`'s stale ADR-003 invariant ("one confirmed arm runs one pass... no branch that selects or starts another chain") gets corrected to describe the bounded-repeat behavior as real/documented — this closes the HELD doc-side twin finding from cycle-51's audit at the same time, per that entry's own note to fold both into one pass.
3. Item 8 in `DECISION-ADR-003-RESIDUAL-7-8` (bounded-repeat contract, currently Pending/human-gated) — check whether this ruling also resolves that item's design questions (pass-count/floor-recheck/value-ceiling scoping) or if it's a distinct residual; update its status accordingly if resolved.
4. `canon/architecture/app-autopilot-model.md`, `canon/architecture/cli-verbs.md`, `canon/testing/test-case-catalog.md` each get the corresponding fix/addition per the scope amendment above.

**Proof:** standard PR ritual — diff-verified, CI green, hub verifies+merges.

**Refs:** `Nebuspace/.samantha/coord/queue-aiclient.md` 2026-08-10T04:46:12Z entry (original escalation) · `canon/ADR/003-discovered-chain-approve-scaffold.md` · orchestrator.md 2026-08-10T19:14:00Z HANDOFF (original) + 2026-08-10T19:18:00Z HANDOFF (scope amendment).

**Sub-parts:** Doc-only WO, solo build, no fan-out needed — 4 files (DECISIONS.md, trade-loops.md, app-autopilot-model.md, cli-verbs.md, test-case-catalog.md — 5 total), independent edits, low risk.
