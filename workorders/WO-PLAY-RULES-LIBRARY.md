# WO-PLAY-RULES-LIBRARY — Play can peek the blessed rule library

**Status:** OPEN · EXECUTE · HIGH · visible client automation · Cursor-only  
**Posted / seeded:** 2026-07-30T04:28Z · hub (after #237 Analyze→bless closes the write path)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `f545747` (Play collects `rule_id`/`do`/`priority` + bless)  
**Refs:** `rules/store.read_rule_store` · `#235` V reflex · `#237` rule identity

## Goal

After Analyze→typed identity→bless (#237), the operator has **no in-client
way to see what landed** in `state/rules/` before pressing `V`. The write
path is closed; the inspect path is still filesystem/CLI spelunking.

Add a **Play-native, read-only** peek of the blessed rule library so the
teach→bless→`V` loop is inspectable without leaving the client.

## Scope

- Thin Play affordance (status-line summary and/or short overlay/popup —
  reuse house patterns; do not invent a second form framework).
- Read via existing `rules.store.read_rule_store` (blessed only; never
  drafts). Branch on `status` before claiming a count (absent / empty /
  partial / unreadable are different operator sentences).
- Show at least: `rule_id`, `do` (macro), `screen_match`, `priority` for
  each blessed rule (truncate honestly if the surface is narrow).
- Focused tests: empty/absent/ok/partial shapes; Play key/intent returns
  no send; product path calls `read_rule_store` (or a thin adapter over it).

## Constraints

- **Read-only.** No edit, delete, promote, arm, or send path.
- Do not change `V` / `reflex_arm` / teach-band token / Analyze identity.
- `#218` `app.py` split still frozen — smallest possible Play wire only.
- No cycles / §A.2 / repeating run-loop / new deps / tooling riders.
- Drafts stay invisible here (same posture as reflex selection).

## Accept

1. From Play, operator can inspect the blessed rule library without leaving
   the client.
2. Absent / empty / ok / unreadable-or-partial each produce an honest
   operator-visible sentence (no fake "0 rules" on a blind store).
3. Listed rows come from `read_rule_store` blessed list only.
4. Focused tests + full suite green.
5. Live prove: `n/a` (filesystem/control read; no TWGS send).

## Proof

```bash
pytest -q tests/test_rules_store.py  # + new focused Play library file
pytest -q tests
```

STATUS names the key/affordance and the empty-vs-blind distinction.

## Follow-on (not this WO)

- Max sacrificial GO: live `V`→`y` arm diversity (#235 NOT-ATTEMPTED).
- Repeating/cycle semantics for `scope: repeating` (core-mechanics; parked).
