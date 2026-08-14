# WO-CANON-DRAFT-TOLL-AND-DEFENSE-CITATION-DRIFT

**Goal:** Re-pin stale `trade_driver.py` / `trade_chain.py` line citations in
`canon/strategy/toll-and-defense.md` Option C fact-find. Substantive claim
(per-step re-validation, fail-closed `_confirmed_send`, no `screen_match`
symbol) remains accurate — only pinpoint cites drifted.

**Depends-on:** none

**Scope:**
- `canon/strategy/toll-and-defense.md` Option C fact-find paragraph
- this WO file

**Out of scope:** product code; other canon files.

**Accept:**
1. Doc cites tip `def` lines for `run_chain` / `_navigate` / `_visit_port` /
   `_confirmed_send` and the live `is_armed`/`should_abort` wiring in
   `session/trade_chain.py`.
2. Nested intra-function cites match tip classify / HOLD / avoid-DANGER
   lines.
3. No product code changes.

**Proof:** tip `sed`/`rg` on cited lines matches claimed content. Live: n/a
(docs-only).
