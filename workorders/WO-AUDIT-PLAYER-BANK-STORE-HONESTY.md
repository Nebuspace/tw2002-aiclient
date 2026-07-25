# WO-AUDIT-PLAYER-BANK-STORE-HONESTY — player_bank.py five-into-one collapse fix

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **IN FLIGHT** 2026-07-25 · discovered by CC during G3 build; dispatched under standing discovered-work rule @ 14:41:45Z · isolated worktree `lane-playerbank-honesty`
> Type: harden · Priority: P1 · Lens: L2 code-vs-canon / honesty
> Refs: `tw2002_aiclient/session/player_bank.py:25-38` `_load_bank_raw` · `canon/architecture/secrets-and-credentials.md`

## Goal
`player_bank.py:_load_bank_raw` collapses five distinct failure conditions into one reassuring empty — same defect class as the menumap and archive `list_skills` fixes. Five conditions collapse into identical `{"version": 1, "players": []}`:
1. File genuinely absent
2. `OSError` (permission denied)
3. `json.JSONDecodeError` (corrupt content)
4. Top level is not a dict
5. `players` is not a list
So `tw players list` reports "no players" for a bank it could not read.

Also: `Path.glob()` silently swallows `PermissionError` — `os.listdir()` raises properly; trap affects any directory-listing path.

## Scope
- `tw2002_aiclient/session/player_bank.py` — `_load_bank_raw` branch on each failure mode
- `tests/` — five-condition probe (each failure → distinct honest result)
- Consumer survey before editing: `cli.py` and `daemon.py` have live single owners; must not touch if consumers live there

## Constraints
- Fenced: consumer survey REQUIRED before editing outside `player_bank.py`
- `player_bank.py` was last touched in `fc8395c` (WO-P1-015); no live lane in it (verified)
- Not on safety list (ungated); dispatched under discovered-work rule
- Isolated worktree; no `git stash`
- One-file-one-total-failure shape (like `cmd_menumap`); not the directory-of-independent-docs shape (like loops store)

## Accept
1. Each of the five failure conditions produces a distinct, honest output
2. "Could not read bank" is clearly distinguishable from "genuinely empty bank"
3. `os.listdir()` or equivalent replaces any `Path.glob()` in this path (PermissionError trap)
4. Consumer API unchanged (existing callers don't break)
5. Full suite green

## Proof
Five-condition probe red→green; STATUS + SHA; Push waits Accept.

## Refs
CC ESCALATION @ 14:41:45Z · `player_bank.py:25-38` · `Path.glob()` PermissionError process note · discovered-work rule (ungated, buildable, disjointness verified)
