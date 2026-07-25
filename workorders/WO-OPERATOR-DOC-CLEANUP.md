# WO-OPERATOR-DOC-CLEANUP — docs/OPERATOR.md cleanup (Max-direct; isolated worktree)


> **SUPERSEDED 2026-07-25** by **WO-DOCS-INTO-CANON** (Max Accepted): `docs/OPERATOR.md` content lives in `canon/surfaces/operator-cold-start.md`; the `docs/` tree is deleted. This WO remains historical.
> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-25 · origin tip **`8b15299`** (hub-landed; was `23acadf` on isolated worktree)
> Type: docs · Priority: P1 · Seat: hub/orchestrator (Max-direct commit)
> Refs: `docs/OPERATOR.md` · `README.md` pointer · hub STATUS @ 14:36:19Z

## Goal
Cleanup of `docs/OPERATOR.md` (non-OKF canonical ops reference):
- Banner: not OKF canon; prefer `canon/` + README
- Retired live `./tw spectate` ops path (F2 WONTBUILD)
- Updated for Ctrl-A Mode (ADR-002)
- Added in-cockpit Spectate + `./tw watch`
- Kept test-pinned phrases (password defer · attach stops runtime trainer · live seat recovery / warp row)

## Scope
- `docs/OPERATOR.md` — content update

## Constraints
- String pins verified (pytest module import blocked by unrelated screens import in that tip — pins asserted directly)
- Push waits Accept
- **Rebase onto current origin** before land (G3 `31c871f` was local-only at time of STATUS — do NOT rebase onto it; landed via cherry-pick onto then-current origin)

## Outcome
`23acadf` on isolated worktree `/tmp/tw2002-operator-doc`. Hub-landed to origin/main as `8b15299` (no Max Accept — Max cannot see worktrees).

## Refs
hub STATUS @ 14:36:19Z · MAX-direct tip `23acadf` · `/tmp/tw2002-operator-doc` off `ae95271`
