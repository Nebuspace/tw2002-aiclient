# WO-AUDIT-SAFE-WIDTH-DOCSTRING — Document `_safe_width` contract

> Status: **DRAFT** 2026-07-25 · Zone-A micro-bank · product tip `bc535d8` **awaits origin** (CC Accept+rebase onto `01bac96`)  
> Type: docs/polish · Priority: P3 · Lens: L4  
> Refs: hub HANDOFF · `cockpit/control_seat.py` `_safe_width` · siblings `_safe_spectating` / `_safe_attached` / `_is_definitively_false`

## Origin note
CC product tip **`bc535d8`** (docstring-only) Accepted @ 06:56Z but **not yet on origin** — rebasing onto Cursor docs `01bac96`. This WO stays **DRAFT** until tip-honesty stamp after `ls-remote` shows the post-rebase SHA. Do not treat as EXECUTED yet.

## Goal
Add the missing contract docstring on `control_seat._safe_width` matching its three siblings (honest-degrade / never-raises / cross-refs) — no behavior change.

## Scope
- A: `tw2002_aiclient/cockpit/control_seat.py` — `_safe_width` docstring only
- B: no test change unless docstring asserts a false contract

## Constraints
Docs/comment only. No seat-key / Human→App. Tip-honesty is a separate Cursor tick after origin lands.

## Accept
Docstring present + sibling-parity; AST/behavior unchanged; suite green.

## Proof
STATUS SHA on origin after CC push · docs tip-honesty stamp. Push waits Accept.
