# WO-CANON-REVERIFY-PRIORITY-ENGINE-13-OBJECTIVE-STATUS

**Goal:** `priority-engine.md`'s 13-objective "Status in code" column had flipped
twice in two weeks on eyeball edits — needed a mechanical grep-based re-verify
of every row's cited symbol against tip, not another eyeball pass.

**Scope:**
- `canon/engine/priority-engine.md` — 3 rows corrected, header re-stamped
- this WO file

**Out of scope:**
- The separate, already-escalated finding that `priority_engine.py` also
  cites `recommend_actions()`/`compose_priorities_lines()` as live functions
  that don't exist in tip (that's a distinct human-ruling item per this
  session's fresh audit, not part of this row's 13-objective table).
- Any code change — this is a doc-accuracy re-verify only.

**Constraints:** every cited symbol grepped directly against
`tw2002_aiclient/` (excluding `tests/`) before either confirming or
correcting a row — no citation trusted from memory or the prior audit pass.

**Findings:**
1. **Row 5** (cargo-hold cost) cited `get_cargo_hold_price()` — does not
   exist. Real function: `introspector.parse_cargo_hold_price()`.
2. **Row 9** (ship-with-larger-holds purchase) cited `_score_upgrade()` —
   does not exist. Real functions: `ship_upgrade_decision.evaluate_candidate()`
   / `choose_upgrade()`.
3. **Row 13** (longest trade-loop chain) cited `chains.longest_profit_chain()`
   — confirmed dead code (zero product callers, docstring-only mentions;
   separately flagged this session in `WO-CLEANUP-DEAD-SYMBOLS-BATCH-2026-08-05`).
   Real live pipeline: `chains.find_profit_chains()`/`find_profit_chains_with_note()`
   + `rank_chains()` (plus `rank_chains_by_yield()` for `tw chains`/`cmd_chains`
   specifically, added PR #527).
4. Rows 1-4, 6-8, 10-12, and the threat row were re-verified and found
   accurate — no change needed.

**Accept:**
1. All 13 objective rows' cited symbols verified to exist in tip via direct
   grep, not memory.
2. 3 stale citations corrected (rows 5, 9, 13); re-verified date stamped in
   the table header.
3. No code changed.

**Proof:** `.venv/bin/python -m pytest tests/test_chains.py tests/test_ship_upgrade_decision.py -n0 -q` → 41 passed (docs-only change, suite unaffected — run for context confirmation only).
