# WO-RULE-WRITER-DRAFTS — persist inert rule drafts under `state/rules/_drafts/`

**Status:** READY · automation frontier (follow-on #221)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/RULE-WRITER-DRAFTS`
**Depends:** `main` ≥ `46ae461` (`tw reflex` + `rules/store.py` on main)

## Goal

Make the reflex library **fillable**: operators (and later AI authors) can persist
**draft** rule documents that `read_rule_store` can list for review, while
**reflex selection stays unchanged** until a human promotes a draft into the
blessed `state/rules/*.json` tree with `approved: true`.

Until this lands, `tw reflex` honestly returns `autopilot_no_candidates` on every
install because no store exists.

## Scope

- **`tw2002_aiclient/rules/writer.py`** — the only module in `rules/` that writes
  rule JSON to disk (mirror `loops/recorder.py` ownership).
- **`rules/store.py`** — teach the reader about **`state/rules/_drafts/`**:
  - Blessed files: `state/rules/*.json` (top level only, unchanged semantics).
  - Draft files: `state/rules/_drafts/*.json`, returned only when
    `include_drafts=True` (mirror `loops/store.py` `DRAFTS_DIRNAME` pattern).
  - Default **`include_drafts=False`** everywhere product paths call today
    (`rules/reflex.py` must stay on the default).
- **CLI:** `tw rule draft …` (or equivalent single subcommand tree) that writes
  a validated document under `_drafts/` and reports the path.
- **Human promote (minimal, in scope):** `tw rule approve <rule_id>` (or
  `promote`) that **only** moves/copies a draft into blessed storage with
  `approved: true` after explicit operator invocation — not automatic, not
  reachable from writer.
- Focused tests + structural guards (writer cannot bless; reflex path ignores
  drafts by default).

## Out of scope

- Wiring reflex into autoloop start / arming / send path.
- §A.2 / `never_auto_action` exemption changes.
- README verb-reference table (DOC-GAP banked).
- `cli.py` / `app.py` line-cap splits (#218).

## Constraints (answers CC pre-questions)

1. **Who may set `approved: true`?** Only the **explicit promote/approve CLI**
   (human act). The **writer must never emit `approved: true`** — hard-coded
   `approved: false` on every write, with a test that attempts to pass
   `approved=True` are refused (fail closed). Aligns with
   `rule-macro-engine.md`: *"Nothing the AI writes … without human approval."*
2. **Where drafts live:** **`state/rules/_drafts/`**, same shape as
   `state/skills/_drafts/`. Store reader gains `include_drafts`; kernel still
   owns “unapproved is absent” at selection time.

## Accept

1. Writer persists only under `_drafts/` with **`approved: false` always**;
   structural test proves writer cannot bless.
2. `read_rule_store(include_drafts=True)` returns draft + blessed rows;
   default call (reflex) **does not** read `_drafts/` — prove with test that
   a draft-only install still yields `autopilot_no_candidates` via `propose_macro`.
3. Round-trip: write draft → load via store → `rule_from_dict` unity preserved
   (no second parser).
4. Promote/approve CLI copies/moves one draft to blessed `state/rules/<id>.json`
   with `approved: true`; only reachable as explicit operator command.
5. At least one **behaviour test** that `tw reflex` (or CLI handler) still
   exits 0 with `autopilot_no_candidates` when only drafts exist (normal today
   until promote).
6. Full offline `suite` green; mutation on writer refuse-bless path where feasible.

## Proof

- Focused tests in `tests/test_rules_writer.py` (new) + store draft listing tests.
- Full offline `suite`.
- Live-prove: **`n/a`** — filesystem + control verbs only; no new TWGS send path.

## Refs

- `canon/architecture/rule-macro-engine.md` (approval, drafts inert)
- `tw2002_aiclient/loops/store.py` (`_drafts`, `include_drafts`)
- `tw2002_aiclient/loops/recorder.py` (writer ownership precedent)
- `workorders/WO-RULE-ENGINE-WIRE.md` · `WO-REFLEX-CLIENT-REACH` (#221)
- CC contract questions 2026-07-29T14:04Z
