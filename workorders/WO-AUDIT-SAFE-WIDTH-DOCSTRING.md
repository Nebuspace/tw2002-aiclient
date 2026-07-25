# WO-AUDIT-SAFE-WIDTH-DOCSTRING — Document `_safe_width` contract

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`c0bdab7`** (CC · Fable 5; rebased Accept of `bc535d8`) · docs stamp Cursor  
> Type: docs/polish · Priority: P3 · Lens: L4  
> Refs: `cockpit/control_seat.py` `_safe_width` · siblings `_safe_spectating` / `_safe_attached` / `_is_definitively_false`

## Tip verdict
**DONE** on origin `c0bdab7` — `_safe_width` carries the sibling honest-degrade / never-raises contract docstring; AST-exec identical to pre-doc tip (behavior unchanged). Proof: hub Accept @ 06:56Z · CC STATUS-DONE @ 09:14:40Z (worktree cherry-pick onto Cursor docs tip; blob parity with `bc535d8`).

## Goal
Add the missing contract docstring on `control_seat._safe_width` matching its three siblings (honest-degrade / never-raises / cross-refs) — no behavior change.

## Scope
- A: `tw2002_aiclient/cockpit/control_seat.py` — `_safe_width` docstring only
- B: no test change unless docstring asserts a false contract

## Constraints
Docs/comment only. No seat-key / Human→App.

## Accept
Docstring present + sibling-parity; AST/behavior unchanged; suite green.

## Proof
STATUS SHA `c0bdab7` on origin. Push waits Accept (product already SHIPped).
