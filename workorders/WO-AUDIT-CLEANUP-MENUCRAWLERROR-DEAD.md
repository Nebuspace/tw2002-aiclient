# WO-AUDIT-CLEANUP-MENUCRAWLERROR-DEAD

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** LOW
**Depends-on:** none
**Gated:** no

## Goal

Remove dead `MenuCrawlError` — defined in `menu/crawler.py`, never raised or caught
(verified tip-wide; no intended-but-unwired WO history found under that name).

## Scope

- `tw2002_aiclient/menu/crawler.py`
- This WO file

## Accept

1. `MenuCrawlError` gone from product tree.
2. live-prove: `n/a` (dead-code delete; crawl behavior unchanged — class was unused).

## Proof

`rg MenuCrawlError` → zero · STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CLEANUP-MENUCRAWLERROR-DEAD`
