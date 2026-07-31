# WO-TEACHBAND-L-CHAINS

**Status:** DONE · origin `8352f3e` (#255) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Depends:** `main` ≥ `f5db859` · `WO-CHAINS-TUI-FULL` (`L` modal live) · HUD #254 shipped

## Goal

Expose the already-shipped Trade-Loop-Chains modal on the calm control strip
by adding canon’s `L)chains` token to the standing teach band — so operators
do not need a hidden-key memory to open `L`.

## Why now

`L` already opens the read-only discovered-chains modal (`cockpit.chains` +
Play handler). The calm band intentionally omitted `L)chains` when no chain
surface existed; that precondition is gone. Canon’s calm reading still lists
`L)chains` before `P panic`.

## Scope (explicit paths)

- `tw2002_aiclient/cockpit/chains.py` — add a single-source `CHAINS_TOKEN =
  "L)chains"` (mirror `REFLEX_TOKEN` / `PANIC_TOKEN` pattern).
- `tw2002_aiclient/cockpit/teachband.py` — import `CHAINS_TOKEN` into
  `TEACH_TOKENS` **immediately before** `PANIC_TOKEN` (keep `A/R/T/V/U`
  order; panic stays last).
- `tests/test_cockpit_teachband.py` — flip the foreign-token pin: assert
  `L)chains` **is** present and imported from `chains.CHAINS_TOKEN`; keep
  `^A)ode` foreign. Update the exact compose string pin.
- `tests/test_cockpit_chains.py` (or adjacent) — pin token spelling shared
  with the key-offer path if a cheap pin fits; do not invent new popup
  behavior.

## Out of scope

- Always-on under-viewport chain bubbles (`WO-PLAY-CHAIN-BUBBLE-VIZ` — next).
- Arming / executing discovered chains.
- Changing the `L` modal contents or draw geometry.
- Adding `^A)ode` to the band.
- Daemon / ensure / live TWGS changes.

## Accept

1. `compose_teach_band()` contains `L)chains` and ends with `P panic`.
2. `CHAINS_TOKEN` is defined once in `chains.py` and imported by `teachband`
   (no second literal spelling of `L)chains` in the band tuple).
3. Existing `L` key still opens/closes the chains popup; no new auto-arm.
4. Focused teachband + chains tests green; full offline suite green.
5. live-prove: `n/a` (chrome label only; no live path).

## Proof

```bash
pytest -q tests/test_cockpit_teachband.py tests/test_cockpit_chains.py
pytest -q -m "not live_login and not pty_ui"
```

## Notes for seat

- Subagent fan-out optional; this is a one-lane list edit + pin flip.
- Do not touch shared operator daemon / `run/`.
- CLAIM → build → STATUS-DONE with SHAs + suite counts.
