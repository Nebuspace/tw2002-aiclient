# WO-TEST-NONTEMPORAL-THRESHOLD-SWEEP

**Goal:** Finish the non-temporal half of the budget-window audit: find count/size/ratio/retry thresholds whose **measured quantity is wider than the name/message claims** (cardinality-for-identity, vacuous floors, etc.).

**Context:** Temporal axis checked clean (#185). One measured non-temporal hit already fixed (#186 badge `len > 10`). CC stopped at first hit rather than expanding GO'd scope — this WO is the rest of that pass.

**Deliverable:** Findings with evidence per site (measure what the control can/cannot catch). Bank fix WOs for real defects; record checked-clean sites. **No product code** in this WO unless a one-line test fix is obviously Accept-complete — prefer bank-then-HANDOFF for fixes.

**Accept:**
1. Sweep report (STATUS or `workorders/` appendix) covering non-temporal thresholds in `tests/`.
2. Each suspect: what it measures, what the message claims, what a realistic silent miss looks like, disposition (KEEP / BANK-FIX / FIXED-inline if trivial).
3. live-prove `n/a`.

**Refs:** CC 19:28:37Z / 19:32:59Z / 19:47:13Z · #186 exemplar.
