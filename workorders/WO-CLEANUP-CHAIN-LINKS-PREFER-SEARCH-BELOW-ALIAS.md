# WO-CLEANUP-CHAIN-LINKS-PREFER-SEARCH-BELOW-ALIAS

**Priority:** LOW  
**Status:** implementing  
**Claimed-by:** impl-aiclient-h1

## Goal

`CHAIN_LINKS_PREFER_SEARCH_BELOW` in `chains.py` was documented as feeding the priority ranking's earn-vs-search band, but no ranking module imported the name — only `MIN_CHAIN_LINKS_TO_EXECUTE` was consumed. Retire the unused alias and make canon tip-honest: `MIN_CHAIN_LINKS_TO_EXECUTE` alone is SSOT for both the execute floor and the earn-vs-search band.

## Scope

- `tw2002_aiclient/chains.py` — delete alias
- `canon/strategy/trade-loops.md` · `canon/engine/priority-engine.md` — fold prose; drop alias
- `tests/test_chains.py` — pin absence + update AST consumer count

## Out of scope

- Inventing a ranking consumer just to keep the name
- Changing numeric thresholds (still 2 / 4)

## Accept

- [ ] Alias gone from product module
- [ ] Canon cites `MIN_CHAIN_LINKS_TO_EXECUTE` as SSOT for earn-vs-search
- [ ] Tests green; pin that alias attribute is absent

## Proof

```bash
.venv/bin/python -m pytest tests/test_chains.py -q -n0
rg -n 'CHAIN_LINKS_PREFER_SEARCH_BELOW' tw2002_aiclient tests
# expect: only historical retirement notes in tests/canon prose, not a live binding
```
