# WO-PLAY-RULE-SCOPE — Play collects rule `scope` (one-shot | repeating)

**Status:** OPEN · EXECUTE · HIGH · visible client automation · Cursor-only  
**Posted / seeded:** 2026-07-30T04:37Z · hub (after #237/#238 teach→bless→peek)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `c6c0d46` (`U)rules` peek on teach band)  
**Refs:** `rule_engine` SCOPE_* · `draft_approve` identity session · Max 2026-07-29 (no invented defaults)

## Goal

Analyze→identity (#237) collects `rule_id` / `do` / `priority` then blesses.
Canon also requires `scope: one-shot | repeating`. Today the bridge omits
scope and the kernel **defaults** to `one-shot` — a minted default on a
human-owned field.

Extend the Play identity session with a **fourth typed field** for `scope`
(literal `one-shot` or `repeating` only). No other spellings. No silent
default when the field is blank.

## Scope

- Extend `create_identity_session` / `resolve_identity_key` (or equivalent)
  so after priority the operator types `scope` (`one-shot` | `repeating`).
- Pass `scope=` into `bridge_to_kernel_document` (already accepts it when
  supplied). Refuse blank / unknown spellings with an operator-visible reason;
  write nothing on Esc/cancel.
- Update focused identity tests: fourth field required; bad scope refuses;
  successful collect lands `scope` on the blessed file.
- Status / labels stay calm and obvious (e.g. `scope (one-shot|repeating)`).

## Constraints

- **No invented default.** Blank scope must not become `one-shot` via a
  silent fallback in the Play path (kernel default is what we are closing).
- **No cycle / repeating run-loop work in this WO.** Arm/`V` remains
  one-pass as today. Storing `repeating` makes the rule *eligible* per
  canon schema; the run-loop that *re-fires* stays parked (separate
  core-mechanics WO). STATUS must say that explicitly.
- Do not change `V` / `reflex_arm` / `U)rules` semantics.
- `#218` `app.py` split still frozen — smallest possible wire.
- No §A.2 / new deps / tooling riders.

## Accept

1. After Analyze `y`, operator supplies `rule_id`, `do`, `priority`, **and**
   `scope` (`one-shot` or `repeating`) before any blessed write.
2. Blank / unknown scope → refuse write; operator-visible reason; nothing
   blessed.
3. Complete fields → blessed file under `state/rules/` carries the typed
   `scope` (not a silent one-shot default).
4. Focused tests + full suite green.
5. STATUS discloses: `repeating` is schema-only until the cycles WO; arm
   still one-pass.
6. Live prove: `n/a` (Play filesystem/control path).

## Proof

```bash
pytest -q tests/test_play_rule_identity.py  # + scope cases / new focused file
pytest -q tests
```

## Follow-on (not this WO)

- Max sacrificial GO: live `V`→`y` arm (#235 NOT-ATTEMPTED).
- Repeating/cycle run-loop rails for `scope: repeating` (core-mechanics).
