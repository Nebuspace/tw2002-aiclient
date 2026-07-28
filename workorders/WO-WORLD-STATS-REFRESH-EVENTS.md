# WO-WORLD-STATS-REFRESH-EVENTS — widen the `known_sectors` refresh, retire its expensive twin

**Status:** OPEN EXECUTE · Cursor preferred · LOW · either seat
**Posted:** 2026-07-28 · impl-claudecode-aiclient (discovered building `WO-GOALS-STATUS-VOCABULARY` T1)
**Depends:** T1 (`world_stats.WorldStats`, `world_model.known_sector_count`) — landed first

## Why this is banked and not folded into T1

The hub's T1 ruling allowed an explore-tick refresh **only** "if you can hook an existing WM read
without new per-draw cost". There is none: outside the new `refresh` call, `app.py` and `screens.py`
contain **zero** `world_model` references (the single grep hit is a comment). Exploration runs
behind `adapters.explore_start_for_profile`, so the writer that would justify a refresh is not on
the client's side of the boundary at all. There is nothing to hook today — this needs an event the
client does not currently receive, which is a design step, not a wiring step.

## Two independent sub-parts (disjoint files — safe to build concurrently)

### A. A second refresh event · `tw2002_aiclient/app.py`, `tw2002_aiclient/world_stats.py`

Today the count is "sectors known as of the last chains popup". An operator who explores for an hour
without opening `L)chains` reads a stale number, and nothing on screen says so. Options, cheapest
first: refresh on explore **completion** (needs a completion signal the client can see); refresh on
any keypress that already pays for a world-model pass; or a min-interval refresh guarded so it can
never land on a draw. **Do not** add a per-draw read — `status_provider()` runs once per draw and the
count is ~26ms at 5000 sectors against a budget already within ~50ms of its ceiling.

**Accept:** a second refresh event exists; a test proves the draw path still performs **zero**
world-model reads; the staleness bound stated in `world_stats.py`'s docstring is updated to match.

### B. Retire the expensive twin · `tw2002_aiclient/trade_adapter.py:647`

```python
known_sectors = len(world_model.all_sectors(world_id, state_dir=state_dir))
```

`all_sectors` reads and deep-copies every sector file; the list is used for nothing but its length
(the next line calls `_class_ports` separately). `known_sector_count` answers the same question
without opening a file — ~157ms → ~5ms at 1000 sectors, ~780ms → ~26ms at 5000.

**Not a pure swap, which is why it is its own sub-part.** The two disagree on a corrupt store:
`all_sectors` raises `WorldModelError`, `known_sector_count` skips the unreadable entry and counts
on. That changes a `PairBuildStats` field feeding the trade/chain finder, so it needs a deliberate
decision about which behaviour is wanted there — not a drive-by edit inside an unrelated WO.

**Accept:** either the call site uses the cheap counter with the corrupt-store behaviour change
pinned by a test, or a comment at that line records why the expensive form is deliberate.

## Refs

- `WO-GOALS-STATUS-VOCABULARY` T1 (`world_stats.py`, `world_model.known_sector_count`)
- hub ruling 2026-07-28T14:04:49Z — "bank one-line follow-on WO — do not block T1 on it"
