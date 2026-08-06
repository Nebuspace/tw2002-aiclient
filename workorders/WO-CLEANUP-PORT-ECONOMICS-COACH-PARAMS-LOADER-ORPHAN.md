# WO-CLEANUP-PORT-ECONOMICS-COACH-PARAMS-LOADER-ORPHAN

**Status:** OPEN (in PR)  
**Priority:** MED  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-39 / queue-aiclient.md · 6-lens aiclient audit 2026-08-05

## Goal

Resolve whether `port_economics.load_coach_port_economics_params` is a missing coach-session wire or dead scaffolding.

## Tip-verify (2026-08-06 @ main `3a532ac`)

| Check | Result |
|---|---|
| Def site | `tw2002_aiclient/port_economics.py:172` |
| Product callers | **0** — only `tests/test_port_economics.py` (2 sites) |
| Coach load path | `cockpit/decisions._kb()` → `coach_kb.load_coach_kb` (full params + strategies) |
| Uses param *values* for cards? | **No** — decisions compose from strategies / upgrade path; no `kb.params` / port-econ key reads |
| Sibling substrate | `hypothesized_floor_prices` etc. **are** wired via `trade_adapter` re-exports |
| CI / schema | `assert_all_unverified_tagged` + hypothesis-tag CI guard cover HypothesisParam tags; this loader additionally requires `COACH_PORT_ECONOMICS_KEYS` ⊆ `params.json` with `verified_vs_live` |

## Decision

**Keep as intentional schema helper — do not wire into coach-session start; do not delete.**

Rationale:

1. Coach already loads the full KB once; a second filtered load at panel start adds I/O without changing rendered cards (no consumer of the returned `CoachParam` tuple).
2. Max carte-blanche (DECISIONS.md § 2026-08-05): port-economics floor/regrowth/plague numbers are **permanently-unconfirmed** — do not invest in live introspection / scoring wire right now. Wiring this loader into live coach composition would front-run that ruling.
3. The function still earns its keep as the **contract test** that `params.json` carries the port-economics coach keys with `verified_vs_live` — complementary to (not duplicate of) `assert_all_unverified_tagged`.

Docstring on the helper updated to say so explicitly so the next unused-code tick does not re-escalate it as an orphan.

## Accept

- [ ] Tip-verify table above stands
- [ ] Helper docstring names intentional test/schema role + no coach-panel wire
- [ ] No behavior change to decisions / trade_adapter
- [ ] Existing `tests/test_port_economics.py` still green

## Proof

```bash
.venv/bin/python -m pytest tests/test_port_economics.py -q -n0
```

## live-prove

`n/a` — verify + docstring only; no live session path.
