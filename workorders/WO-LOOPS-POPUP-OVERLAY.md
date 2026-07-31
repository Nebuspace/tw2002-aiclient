# WO-LOOPS-POPUP-OVERLAY

**Status:** READY · EXECUTE · MED · after #297 on `main`
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/LOOPS-POPUP-OVERLAY`
**Depends:** DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 6 · teachband `L)ist Loops` (#297) · existing `cockpit.chains` + center draw

## Why

Max ruled **`L` = overlay popup on the game viewport** (list learned loops for select; `T` runs). As-built already draws `ChainsSession` over `regions["center"]`, but chrome/token still say `L)chains` in places, and the overlay should read as a **modal on the GAME**, not a leftover strip library spelling.

## Goal

Polish the loops list into a clear viewport overlay titled/taught as **List Loops**, without rewriting arm/confirm money-path.

## Scope

1. **Vocabulary:** Align operator-facing strings with `L)ist Loops` (`LOOPS_TOKEN` / teachband). Update `CHAINS_TOKEN` or add alias so HELP / empty states / titles do not teach `L)chains` as the calm label. Keep `L` key binding.
2. **Overlay geometry:** Modal remains boxed over the **center/GAME** region (not left/right gutters, not full-frame). Title row + scrollable list; Esc/close unchanged.
3. **Select → T:** Existing select + `T` / Enter→armconfirm path stays; do not invent a second spend path. Document in HELP one line: List Loops picks; Trade Loop Chain runs.
4. **Pins:** Layer-A compose + at least one PTY/visible pin that overlay title/`L)ist Loops` (or List Loops header) appears when open over center; old `L)chains` calm-label pins updated.
5. This WO file on the branch.

## Out of scope

- Discover/EV engine changes · #283 money-path diversity · teachband group/CONN (done #297) · Rules-library overlay.

## Constraints

- Money-path: Enter still arms via confirm gate (or App-armed policy already on main) — do not make bare Enter silent-spend for Manual.
- No new deps · no force-push · no secrets in STATUS.

## Accept

1. Opening `L` paints a boxed list over the GAME viewport region.
2. Calm chrome / HELP teach **List Loops** (not `L)chains` as the primary label).
3. Select + run path still works (pins green).
4. Focused + full suite green; live-prove per hub (chrome-heavy may be `n/a` with reason **only if** no play/session path touched — else diversity).

## Proof

`pytest` focused chains/teachband/visible pins + suite. STATUS with tip SHA. Do not self-merge.

## Refs

- Plan `.samantha/plans/play-strip-autonomy-keys.md` wave 4
- `cockpit/chains.py` · `screens.py` center draw ~2202 · `teachband.LOOPS_TOKEN`
