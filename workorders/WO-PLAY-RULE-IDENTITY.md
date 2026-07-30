# WO-PLAY-RULE-IDENTITY — Play collects rule_id / do / priority for Analyze drafts

**Status:** OPEN · EXECUTE · HIGH · visible client automation · Cursor-only  
**Posted / seeded:** 2026-07-30T04:10Z · hub (closes Analyze→`V` loop after #235/#236)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `fd24246` (`V)reflex` on teach band; reflex arm LIVE)  
**Refs:** `cockpit/draft_approve.py` · Max 2026-07-29 (no invented defaults) · `#235` Play reflex

## Goal

After Analyze `y`, Play today accepts a **proposal** and prints a CLI bridge
command (`tw rule draft --rule-id ID --do MACRO --priority N`) because the
cockpit has no typed-entry path. Until those three fields are human-supplied,
`V` always proposes nothing on a fresh install — automation stays outside the
client.

Add a **Play-native** path that collects `rule_id`, `do` (macro name), and
`priority` from the operator (no minted defaults), then writes an inert draft
via the existing `rules.writer.write_draft` / `promote_draft` path so a later
`V`→`y` can arm a real rule.

## Scope

- Thin typed-entry affordance in Play (status-line / control-strip prompt
  session is fine; reuse house patterns if a minimal text-entry helper
  already exists — do not invent a second form framework).
- Wire after Analyze draft acceptance (or as the approve path itself) so the
  three fields are collected **before** any blessed `state/rules/` write.
- Call existing `write_draft` → `promote_draft` (or the bridge helpers in
  `draft_approve.py`); **no** second bless API.
- Update / replace the CLI-only status line: on success, status should say a
  rule was written (id + macro) and that `V` can propose it — not "run tw rule
  draft…".
- Focused tests: refuse empty/whitespace fields; refuse non-int priority;
  successful collect → draft then blessed file; `propose_macro` / FakeClient
  reflex sees the new rule; no defaults minted when fields omitted.

## Constraints

- **No invented defaults** for `rule_id` / `do` / `priority` (Max ruling).
- Esc / cancel aborts with nothing written to blessed storage.
- Do not change `reflex_arm` / `V` key semantics / teach-band token.
- `#218` `app.py` split still frozen — smallest possible Play wire only.
- No §A.2 / cycles / new deps / tooling riders.
- Live successful arm of the new rule still Max-gated turn-spend; this WO's
  live prove is offline filesystem + FakeClient unless hub asks otherwise.

## Accept

1. From Play Analyze→approve path, operator can supply `rule_id`, `do`,
   `priority` without leaving the client.
2. Missing/blank fields → refuse write; operator-visible reason; nothing
   blessed.
3. Complete fields → inert draft then promote via existing writer; file lands
   under `state/rules/` with `approved: true`.
4. Offline: after that path, `reflex_propose` (or equivalent FakeClient) can
   select the new rule for the matching screen class.
5. Focused tests + full suite green.
6. Live prove: `n/a` (Play filesystem/control path; no required TWGS send).
   Note separately if a live arm prove of #235 remains `NOT-ATTEMPTED`.

## Proof

```bash
pytest -q tests/test_draft_approve_bridge.py tests/test_play_reflex_arm.py  # + new focused file
pytest -q tests
```

STATUS names the entry UX (how the three fields are typed) and the on-disk
rule path shape.

## Follow-on

- Max sacrificial GO: live `V`→`y` arm diversity on a sacrificial profile.
- Repeating/cycle semantics for armed reflex (separate WO).
