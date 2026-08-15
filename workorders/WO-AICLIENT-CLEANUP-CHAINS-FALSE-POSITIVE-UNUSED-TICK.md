# WO-AICLIENT-CLEANUP-CHAINS-FALSE-POSITIVE-UNUSED-TICK

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1  
**Result:** DONE (tip-honest closeout — no product code change)

## Goal

Close the unused-code-tick false positive that flagged
`CHAIN_LINKS_PREFER_SEARCH_BELOW` as a live test-only symbol after it was
already retired.

## Tip-check (same action)

| Check | Result |
|---|---|
| Product symbol | Absent — retired in PR #725 (`d7e8e49`); `chains.py:49` is now `MIN_CHAIN_LINKS_FOR_SHIP_UPGRADE` |
| Negative pin | `tests/test_chains.py` keeps `assert not hasattr(..., "CHAIN_LINKS_PREFER_SEARCH_BELOW")` |
| Fresh sweep | `unused-code-20260815T1109Z.md` — **zero** `CHAIN_LINKS_PREFER*` subjects |
| Disposition | `tw2002_aiclient.chains:CHAIN_LINKS_PREFER_SEARCH_BELOW` → `false_positive` in `.samantha/audit/unused-code-disposition.json` |
| Propose | `unused-code-tick.py --force --propose 20` → `proposed=0` for this subject (ledger skip) |

## Why no `find-unused-code.py` patch

`_RefCollector` only records AST **Name** loads. A negative-existence pin's
string (`hasattr(mod, "CHAIN_LINKS_PREFER_SEARCH_BELOW")`) is a **Constant**,
so it never counts as a live reference. The stale
`unused-code-20260815T0038Z.md` row was a **pre-retire** snapshot (alias still
defined; tests still Name-referenced it). Tip honesty + disposition closes the
class; inventing a hasattr-string filter would not change tip findings.

## Accept

- [x] Tip rescan does not list `CHAIN_LINKS_PREFER_SEARCH_BELOW`
- [x] Disposition marked `false_positive` with this WO id in notes
- [x] Negative-existence pin retained in `tests/test_chains.py`
- live-prove: **n/a** (docs + hub disposition ledger; no send/session path)

## Proof

```bash
python3 ../.samantha/scripts/find-unused-code.py --repo . --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert not any("CHAIN_LINKS_PREFER" in str(f) for f in d["findings"])'
rg -n 'CHAIN_LINKS_PREFER' tw2002_aiclient/ tests/
# expect: only tests/test_chains.py hasattr-negative pin
```
