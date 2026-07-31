# WO-PLAY-CHAIN-BUBBLE-VIZ

**Status:** DONE · origin `fb33f5b` (#256) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Depends:** `main` ≥ `8352f3e` · `WO-CHAINS-LIVE-REFRESH` · `WO-CHAINS-TUI-FULL` · `WO-TEACHBAND-L-CHAINS`

## Goal

While Play explores and discovers priced linked ports, show the **best
discovered profit cycle** as an always-visible five-row sector bubble strip
directly beneath the game viewport — without pressing `L`. `L)chains` remains
the detailed read-only modal.

## Why

`ChainScalars` only retains `(hops, unit)`. Idle refresh already discovers a
ranked chain, then throws the sector sequence away. Canon’s `[CHAIN]` bubble
row (`compose_chain_bubbles`) existed pre-rebirth and was deleted with
`twclient`. Operators currently see linked ports but no cycle visualization.

## Explicit lanes (∥ build-wave — disjoint files)

### Lane A — latest trustworthy best-chain cache
**Paths:** `tw2002_aiclient/chain_status.py` · `tests/test_chain_status_coach_wire.py`
- Extend `ChainScalars` (or sibling) to retain a **read-only** best discovered
  chain object/sequence alongside existing hop/unit scalars.
- Both idle refresh and the `L` open path already call `update(discovered)` —
  wire retention there.
- Failed / inconclusive discovery must **not** erase the last good sequence.
- Completed empty discovery paints quiet empty (no fabricated “unknown”).
- Never put the full chain object on daemon `status` JSON.
- Never recompute / filesystem-read during draw.

### Lane B — pure bubble composer
**Paths:** new `tw2002_aiclient/cockpit/chain_bubbles.py` · new
`tests/test_cockpit_chain_bubbles.py`
- Port useful semantics from pre-rebirth `4a11a36:twclient/spectate_layout.py`
  (`compose_chain_bubbles`, `chain_bubble_sectors`, `CHAIN_VIZ_H = 5`).
- Always exactly five lines; empty → quiet empty state; current sector ★;
  unknown port class `?`; width clip with deterministic `… Nh`.
- Pure strings only — no curses, no discovery imports, never raises on hostile
  shapes.
- Prefer contiguous known-port bubble behavior if the historical follow-ups
  (`af4c230` / `1e9ad1d`) are cheap to include; otherwise pin `4a11a36` and
  note the gap.

### Lane C — geometry + draw wire
**Paths:** `tw2002_aiclient/cockpit/layout.py` · `tw2002_aiclient/screens.py` ·
`tests/test_cockpit_layout.py` · new `tests/test_play_chain_bubbles_visible.py`
- Optional `chain` region: `y = center.y + center.h`, `x/w = center`, `h = 5`.
- Fold to `None` unless **five wholly spare rows** exist after preserving
  bordered 80×25 center, LOGS, STOP/intervention, and control strip.
- **Hard rule:** never shrink the native 80×25 viewport to make bubbles fit.
- Draw cached best chain read-only; current sector from
  `status["hud"]["sector"]["value"]`.
- Draw path must not call chain search / filesystem.

## Out of scope

- Arming / executing discovered chains from bubbles or modal.
- Changing `L` modal contents beyond reading the shared cache.
- Daemon / ensure / live TWGS protocol changes.
- Broader cockpit redesign.

## Accept (falsifiable)

1. Synthetic explored world with compatible priced linked ports paints the
   ranked `chains[0]` sector cycle beneath the viewport **without** pressing
   `L` (idle refresh or equivalent client update).
2. Current sector is ★-marked; cycle does not bridge through a non-port sector
   (per chosen composer rule).
3. Empty, partial/truncated (`… Nh`), and unavailable/inconclusive discovery
   are visually distinct; failed update never wipes last good cycle.
4. Draw performs no chain search and no filesystem read (structural pin).
5. Insufficient height → chain region folds; center stays 80×25; no overlap
   with LOGS / STOP / control strip.
6. `L` still opens the full modal; discovered rows remain structurally
   non-armable (`tests/test_play_chains_discovered.py` stays green).
7. Focused tests + full offline suite green.
8. live-prove: Play chrome / offline PTY or recording-window proof preferred;
   full TWGS diversity **not** required for this chrome WO — post honest
   `n/a` with reason **or** a single safe RETURNING visual cell if cheap.
   Never claim live diversity you did not run.

## Proof

```bash
pytest -q tests/test_chain_status_coach_wire.py \
  tests/test_cockpit_chain_bubbles.py \
  tests/test_cockpit_layout.py \
  tests/test_play_chain_bubbles_visible.py \
  tests/test_play_chains_discovered.py \
  tests/test_live_refresh.py
pytest -q -m "not live_login and not pty_ui"
```

## Seat notes

- Fan out Lanes A/B/C as parallel workers, then integrate.
- Do not touch shared operator `run/` daemon.
- CLAIM → build on HANDOFF branch in **your** worktree → STATUS-DONE with
  SHAs + suite counts + which Accept bullets are proven how.
- Hub worktree idle at `/private/tmp/hub-play-chain-bubble-viz`.

## Refs

- Plan: Nebuspace `.samantha/plans/trade-loop-chain-visibility-2026-07-30.md`
- Historical: `4a11a36:twclient/spectate_layout.py` (`compose_chain_bubbles`)
- Cache today: `chain_status.py` `ChainScalars` (hops/unit only)
- Refresh: `cockpit/live_refresh.py`
