# WO-CANON-FIX-PRIORITY-ENGINE-GOALS-FOCUS-STALE-CITATIONS

**Goal:** Fix internal citation drift in `canon/engine/priority-engine.md`
§ Two-layer information architecture. That section named nonexistent
`GoalsSnapshot` / `compose_primary_goals_lines()` / `compose_priorities_lines()`
→ `recommend_actions()` as the GOALS/FOCUS panel path; tip uses
`cockpit/goals.py:compose_goals_lines` and
`cockpit/focus.py:compose_focus_lines` fed by
`focus_status.recommend_focus_candidates` — already cited correctly earlier in
the same file.

**Depends-on:** none (docs-only)

**Scope:**
- `canon/engine/priority-engine.md` § Two-layer information architecture
- this WO file

**Out of scope:** other canon files that still mention archive
`compose_primary_goals_lines` names; product code; changing
`priority_engine.recommend_actions` strategic-ranker prose elsewhere in this
doc (that function still exists for coaching/ranking — it is not the FOCUS
panel composer).

**Accept:**
1. § Two-layer IA cites tip GOALS/FOCUS composers with zero hits for the
   stale symbol quartet in that section.
2. No product code changes.

**Proof:** `rg` the four stale names in the Two-layer section → empty; tip
`def` lines for the three real functions exist. Live: n/a (docs-only).
