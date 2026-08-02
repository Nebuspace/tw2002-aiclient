# WO-REFLEX-CLIENT-REACH — client path for daemon `reflex` verb

**Status:** DONE · origin `46ae461` (#221) · tip-honesty stamp 2026-08-02 (product on main; banner was stale READY)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/REFLEX-CLIENT-REACH`
**Depends:** `main` ≥ `0a11241` (`rules/reflex.py` + protocol dispatch LIVE)

## Goal

Give operators and the cockpit a **read-only** client reach into the daemon
`reflex` verb so `propose_macro` / `select_rule` answers are visible outside
unit tests. No new game sends; no rule authoring in this slice.

## Scope

- **`adapters.py`:** typed `reflex_propose(...)` (or equivalent) mirroring other
  control verbs — never-raises transport, structured result.
- **`session/cli.py`:** expose `tw reflex` (or subcommand) that prints JSON /
  honest text from the adapter; document read-only.
- **Optional (only if trivial):** one cockpit read path that surfaces the latest
  reflex decision on an existing status/diagnostics surface — **do not** invent
  new chrome if it blows scope; CLI alone satisfies Accept.
- **Tests:** FakeClient/unit for adapter + CLI dispatch; reuse patterns from
  `test_rules_reflex.py` where sensible.

## Out of scope (separate WO)

- Rule **writer** / creating `state/rules/*.json` files
- Wiring reflex output into autoloop start or macro execution
- §A.2 / `never_auto_action` changes

## Constraints

- Read-only control verb — **no** keystroke send path added.
- Preserve two inert landings documented in `rules/reflex.py`.
- Behaviour search before Accept: confirm adapter/CLI do not already exist.

## Accept

1. Adapter round-trips daemon `reflex` success/stop shapes without raise.
2. CLI invokes adapter and renders decision (macro name or STOP reason).
3. Focused tests + full offline `suite` green.
4. STATUS states rule-writer still absent (library may be empty).

## Proof

- `pytest` adapter + CLI modules; full `suite`.
- Live-prove: `n/a` (control verb only; no new TWGS send path).

## Refs

- CC 13:43Z collision note (this slice, not rule writer)
- `workorders/WO-RULE-ENGINE-WIRE.md`
