# WO-BUILD-NO-COLLUSION-BANNER-ROTATION-TOUCHPOINT — tip-stamp bank banner

**Status:** IN FLIGHT · Cursor · `wo/BUILD-NO-COLLUSION-BANNER-ROTATION-TOUCHPOINT`  
**Posted:** Cycle-43 LOW · queue-aiclient.md

## Goal

Verify-first tip-close: launcher `BankViewScreen` already paints
`BOUNDARY_LINE_1` / `BOUNDARY_LINE_2`. Correct the stale "not shown" claim in
`entry-and-profile-selection.md`. Pin the banner in the bank pty proof.
Residual: no `tw players list` CLI yet — note it must reuse the same lines.

## Accept

1. Canon names the live TUI banner + CLI residual honestly.
2. Bank empty-list pty proof asserts both boundary lines.
3. live-prove `n/a` (docs + offline pty pin).

## Refs

- `screens.py::BOUNDARY_LINE_1/2` · `BankViewScreen.draw`
- `canon/surfaces/entry-and-profile-selection.md`
