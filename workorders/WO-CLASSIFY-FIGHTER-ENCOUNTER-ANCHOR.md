# WO-CLASSIFY-FIGHTER-ENCOUNTER-ANCHOR — the toll `Option?` prompt has no gate anchor

**Status:** OPEN · EXECUTE · HIGH · hub ruling **(a)** 2026-07-28 (armed-eligible `fighter_encounter`; Max combat GO entailed)
**Seat:** Claude Code (`impl-claudecode-aiclient`) · Live DEFERRED → Cursor
**PR branch:** `wo/CLASSIFY-FIGHTER-ENCOUNTER-ANCHOR`
**Found:** 2026-07-28 by `impl-claudecode-aiclient` while executing `WO-COMBAT-ENCOUNTER-POLICY-EXEC`
**Refs:** `canon/DECISIONS.md` §A.2 + §A.2 clarification · `canon/strategy/toll-and-defense.md` § Toll-dialogue guard behavior (I5) · `tw2002_aiclient/session/classify.py` (`_GATE_ANCHORS`, `NEVER_AUTO_ACTION_CLASSES`)

## The finding (measured, not inferred)

`classify_screen()` today, on this branch:

| frame | class returned | verdict |
|---|---|---|
| `Corp fighters block your path.` + vs-line + `Option? (A,D,I,R,S,?):?` | `unknown` | **safe** — canon's stop-and-escalate trigger |
| `Fighters: 4 (Somecorp) [Toll]` + `Option? (A,D,I,R,P,S,?):?` | `unknown` | **safe** |
| `Sector : 42 …` + `Corp fighters block your path.` + `Option? (A,D,I,R,S,?):?` | **`sector_display`** | ⚠️ **the hole** |
| `How many fighters do you wish to use (0 to 250) [0]?` | `money_prompt` | safe (never-auto-action; guarded bounded qty exempt per §A.2 clarification) |

The third row is the normal live case — you warp, the previous sector body is still
painted, and the toll dialogue lands underneath it. The server is **blocked** on
`Option?`, but the screen is handed to the rest of the app wearing `sector_display`:
an ordinary, teachable content class. Any taught rule or macro matching
`sector_display` may then fire a keystroke into a live combat prompt.

This is the exact hazard `classify.py`'s own `money_prompt` comment describes for the
StarDock purchase screen — *"the screen would carry a benign, teachable identity while
the server sat blocked"* — reproduced for combat. There is no gate anchor for the
encounter prompt, so the content anchor wins whenever a body is on screen.

`warp_confirm` is the in-file precedent and carries the identical rationale:
*"Mid-warp Y/N (live stall): must beat sector_display when the Sector body is still on
screen above this prompt."* The encounter prompt is structurally the same shape and has
no equivalent.

## Why this was NOT fixed inside the combat WO

`WO-COMBAT-ENCOUNTER-POLICY-EXEC` constrains: *"No canon invent beyond Max amend on this
branch."* Adding a returnable class is a vocabulary change the module argues is
**monotone in the dangerous direction** — *"every label added is a screen moved from
'must escalate' to 'may be taught'"* — and `NEVER_AUTO_ACTION_CLASSES` membership is
governed by `DECISIONS.md` §A.2. That is a ruling, not an implementation detail.

**No live exposure today:** `fighter_toll_policy` has no product consumer
(`grep` across the package: zero non-test importers), so nothing currently acts on
either classification.

## Vocabulary ruling (RESOLVED — hub 2026-07-28)

A new `fighter_encounter` class must be one of:

- **(a) auto-action-eligible when armed** — the shape §A.2's clarification explicitly
  blesses (*"or later earn a dedicated haggle class that is auto-action-eligible when
  armed"*), with `fighter_toll_policy` as the single guarded owner. Enables #206's
  policy to actually run.
- **(b) in `NEVER_AUTO_ACTION_CLASSES`** — names the screen and forbids it. Closes the
  `sector_display` hole but makes auto-Retreat impossible, defeating the Max-ratified
  gate.

**Ruled (a).** Armed-eligible `fighter_encounter` so `fighter_toll_policy` can own the screen. Qty stays `money_prompt`.

## Accept

1. A gate anchor matching `Option? (A,D,I,R[,P],S,?)`, placed with the `warp_confirm`
   rationale (before the content anchors) so a stale sector body cannot claim the frame.
2. Class membership per Max's ruling above, with the reasoning written into the anchor
   comment in the style of the surrounding entries.
3. Blast-radius proof: classify fixtures + synthetic frames before and after; **exactly 3 rows move** (CC oracle baseline):
   - toll banner + vs-line + `Option? (A,D,I,R,S,?)` → `unknown` → `fighter_encounter`
   - `Fighters: N (Corp) [Toll]` + `Option? (…,P,…)` → `unknown` → `fighter_encounter`
   - `Sector : 42` above encounter prompt → `sector_display` → `fighter_encounter`
   Any other class change = fail. Qty frame (`How many fighters…`) **stays `money_prompt`**.
4. Pins for all four rows in the finding table, including the `sector_display` hole as the regression that motivated it.
5. Class is **(a) auto-action-eligible when armed** — NOT in `NEVER_AUTO_ACTION_CLASSES`. Comment cites §A.2 clarification + `fighter_toll_policy` as guarded owner.
6. Suite green · live DEFERRED → Cursor. Do **not** wire policy consumers in this WO (wire follows).

## Constraints

Safety-list adjacent (screen vocabulary governs what may be driven). Public-safe.
Do not widen the regex to bare `Option?` — that shape is not exclusive to the toll
dialogue.
