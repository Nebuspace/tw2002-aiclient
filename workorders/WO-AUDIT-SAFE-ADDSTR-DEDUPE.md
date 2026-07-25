# WO-AUDIT-SAFE-ADDSTR-DEDUPE — Unify screens._safe_addstr with draw choke

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`29fd76c`** (CC · Fable 5; amended after REVISE) · docs stamp Cursor  
> Type: polish · Priority: P2 · Lens: L4  
> Refs: `screens.py:_safe_addstr` · `cockpit/draw.py:safe_write` · `tests/test_safe_addstr_choke.py`

## Tip verdict
**DONE** on origin `29fd76c` — `_safe_addstr` is a thin one-line wrapper over public `safe_write` (draw choke: control-char sanitize + cell-width clip); ~25 call sites kept by name. Operator-typed create-form echo no longer reaches `addstr` raw (CSI neutralized). Last-column clip parity disclosed (true `max_x-1`). **REVISE note:** red-first loader pins `_PRE_FIX_TIP = "7cd9ea9"` (never bare `HEAD:`). Proof: choke suite 8/8 · full suite green at Accept.

## Goal
Retire the less-hardened `screens._safe_addstr` duplicate: reuse draw choke (control-char sanitize + cell-width clip) for operator-typed echo and bank metadata.

## Scope
- A: `screens.py` — call into draw helper / shared util
- B: `cockpit/draw.py` — export if needed; keep one choke
- C: tests — echo/clip matrix; no visual seat-key change

## Constraints
3-screen rendering change → own WO (this). No attach/M semantics. No HARDEN reopen.

## Accept
One write primitive; `_safe_addstr` gone or thin wrapper; clip/sanitize parity with draw.

## Proof
Unit + optional pty · STATUS SHA `29fd76c` on origin. Push waits Accept (product already SHIPped).

## Refs
CC Zone-A @ 05:27:02Z · hub REVISE @ 06:11:47Z · Accept @ 06:21:14Z
