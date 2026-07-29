# WO-DRAFT-APPROVE-KERNEL-BRIDGE — cockpit Analyze approval → kernel rule store

**Status:** READY · visible automation (follow-on #222)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/DRAFT-APPROVE-KERNEL-BRIDGE`
**Depends:** `main` ≥ `974a8a8` (rule writer + promote on main)

## Goal

Close the dual-vocabulary gap: cockpit Analyze `y/N` must become a path that
can put a **kernel-schema** rule into `state/rules/` via the existing writer /
promote path — so an operator who approves something can later see `tw reflex`
change its answer. Today `y` sets in-memory flags and persists **nowhere**.

## Max ruling (2026-07-29)

**Bridge**, not honesty-rename. **No invented defaults** for `rule_id`, `do`
(macro name), or `priority` — the human must supply those before a document may
be blessed. Minting a default priority is forbidden (would collide AI rules into
`autopilot_ambiguous_rules`).

## Scope

- Teach Analyze / `draft_approve` to produce or accept a **kernel-shaped** draft
  (`rule_id`, `screen_match`, `do`, `priority`, optional `guards`) that
  `rule_from_dict` admits.
- Persist inert drafts only through `rules.writer.write_draft`
  (`approved: false` always).
- On human confirm (`y`), call the existing **`promote_draft`** path — do **not**
  invent a second bless API inside cockpit.
- Refuse promote (operator-visible) when `rule_id` / `do` / `priority` are
  missing or when `do` is empty/`None`.
- Update / invert
  `tests/test_rules_writer.py::test_the_cockpit_analyze_draft_cannot_enter_the_rule_store`
  — that tripwire is expected to go red; replace with pins that the bridged
  shape **does** round-trip into the store, and that the old stub shape still
  cannot silently bless.
- UX honesty: status / labels must not claim "playback-eligible" for reflex
  until a blessed file exists under `state/rules/`.

## Out of scope

- Wiring reflex into autoloop start / arm / send.
- §A.2 / `never_auto_action` changes.
- `#218` `app.py` split.
- Honesty-rename-only path (ruled out).

## Accept

1. A complete kernel draft (human-supplied `rule_id`, `screen_match`, `do`,
   `priority`) written from the Analyze/approve path lands under
   `_drafts/` with `approved: false`, then `y` promotes via `promote_draft` to
   blessed `state/rules/` with `approved: true`.
2. Missing `rule_id` / `do` / `priority` → promote refused; nothing blessed;
   operator-visible reason. **No defaults minted.**
3. Old `{when, do:None, source, playback_eligible}` stub alone still cannot
   pass `rule_from_dict` / `write_draft` (negative pin retained).
4. After promote, `propose_macro` / `tw reflex` can select the new rule for that
   screen (offline test with real store files — not a hand-built reply dict).
5. Tripwire test updated: former "cannot enter" marker replaced with
   deliberate before/after pins + docstring noting the reconcile.
6. Full offline `suite` green; live-prove **`n/a`** (filesystem + control path;
   no new TWGS send).

## Proof

- Focused tests: bridge write → promote → reflex sees macro; refuse-without-
  fields; old stub still refused.
- Full offline `suite`.
- Live-prove: `n/a` with reason.

## Refs

- CC decision input 2026-07-29T14:41Z
- `cockpit/draft_approve.py` · `cockpit/assign_trigger.py`
- `rules/writer.py` · `rules/store.py` · `rules/reflex.py`
- tripwire in `tests/test_rules_writer.py`
- Max: visible automation; human supplies identity/macro/priority
