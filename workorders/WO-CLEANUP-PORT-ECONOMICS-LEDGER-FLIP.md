# WO-CLEANUP-PORT-ECONOMICS-LEDGER-FLIP

**Status:** DONE · tip  (PR #648)
**Priority:** LOW  
**Claimed-by:** impl-aiclient-cursor  
**Source:** queue-aiclient.md · audit 2026-08-09

## Goal

Stop unused-code tick from reopening `port_economics.all_hypothesis_params` /
`assert_all_unverified_tagged` as `tip_check`. They are live CI regression
guards (`scripts/hypothesis_tag_ci_guard.py`) but the finder treats
`scripts/` + tests as non-product, so a ledger-only flip reopens every Half-2.

## Verify-first (origin/main `ee05b079`)

| Check | Result |
|---|---|
| CI caller | `scripts/hypothesis_tag_ci_guard.py` calls both |
| Tests | `tests/test_port_economics.py` |
| App boot | **no** product caller (unlike `assert_coverage_map_intact`) |
| Disposition | `tip_check` reopened 2026-08-10T00:44Z after prior resolved flip |

## Diff

- `tw2002_aiclient/app.py` — boot assert + `all_hypothesis_params()` read
  beside action-safety / imperative denylist (`--help` still exempt)
- `tests/test_port_economics_hypothesis_startup_wire.py` — wire pin
- This WO file

Nebuspace `.samantha/audit/unused-code-disposition.json` flip is hub/seat
coord hygiene (outside this repo PR); product wire is the durable close.

## Accept

- [x] `assert_all_unverified_tagged` + `all_hypothesis_params` called from `app.main`
- [x] `--help` path unchanged (no assert I/O)
- [x] Targeted pytest green

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_port_economics.py \
  tests/test_port_economics_hypothesis_startup_wire.py -q -n0
```

## live-prove

`n/a` — offline boot pin; no live session path.
