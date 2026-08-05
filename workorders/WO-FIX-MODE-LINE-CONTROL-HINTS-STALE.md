# WO-FIX-MODE-LINE-CONTROL-HINTS-STALE

## Goal
Remove the stale tip-honesty that admits `CONTROL_HINTS = "M)ode …"` as as-built —
that constant is gone from product Python; Mode is Ctrl-A on the chip (ADR-002).

## Scope
- `canon/surfaces/mode-line-and-teach-controls.md`
- this WO file

## Accept
1. Doc no longer claims tip still ships `CONTROL_HINTS = "M)ode …"`.
2. Responsive-fold length-budget note no longer cites the dead constant.
3. Tip trainer band + `^A)` chip wording remain accurate.
4. No product Python change required (constant already absent).

## Proof
- `git grep -n 'CONTROL_HINTS.*"M)ode' -- canon/` → empty for this concept
- `git grep -n CONTROL_HINTS -- '*.py'` → empty on tip
- offline suite; live-prove n/a (docs)

## Out of scope
Re-key Assign-Trigger · rewrite full explore band · multiplexer Ctrl-A hazard (already noted)
