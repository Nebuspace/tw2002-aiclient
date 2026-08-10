# WO-CANON-FIX-CLI-VERBS-FRAMES-LIVE-LIST

**Goal:** Tip-true the Implementation status LIVE `tw` verb enumeration in
`canon/architecture/cli-verbs.md` so it includes `frames` (already catalog-LIVE and
wired via `frames_cli.add_frames_parsers`).

**Depends-on:** `WO-BUILD-CLI-VERBS-FRAMES` / #642 catalog TARGET→LIVE close (`f3b2f33`) —
catalog row + citations already honest; this WO closes the residual omission in the
enumerated LIVE list (and the stale tip-SHA stamp on that block).

**Scope:**
- `canon/architecture/cli-verbs.md` — Implementation status LIVE list + tip SHA /
  re-verify date; Code Divergence #1 tip pin if it still cites the pre-frames SHA.
- `workorders/WO-CANON-FIX-CLI-VERBS-FRAMES-LIVE-LIST.md` — this file.

**Constraints:**
- Docs-only. Do not invent new CLI verbs or change `build_parser()`.
- Skip Max-gated `WO-ESCALATE-BOUNDED-REPEAT-*`.
- Prefer explicit alphabetical insertion of `frames` after `explore`.

**Accept:**
- LIVE enumeration includes `frames`.
- Tip SHA / re-verify date match the tip this WO lands on (not leftover `13153a6` /
  2026-08-09 alone).
- Catalog row remains LIVE; no TARGET regression.
- Parenthetical "tip-true set" no longer contradicts the enumerated list.

**Proof:** `git show` of the LIVE list lines; confirm
`tw2002_aiclient/frames_cli.py` still registered from `session/cli.py`
(`add_frames_parsers`); docs-only → live-prove n/a.

**Refs:** `canon/architecture/cli-verbs.md` § Implementation status · catalog
`frames {tail,show,grep,diff}` · `session/cli.py` + `frames_cli.py` · tip
`origin/main@f14cc305` (#669).
