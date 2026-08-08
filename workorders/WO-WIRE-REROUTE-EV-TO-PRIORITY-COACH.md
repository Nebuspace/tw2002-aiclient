# WO-WIRE-REROUTE-EV-TO-PRIORITY-COACH

**Status:** READY · gated: no
**Posted:** 2026-08-08 · orchestrator HANDOFF (unused-wire tranche 2, background triage)

## Goal
reroute_vs_fight.py has zero product callers outside its own file/tests. Wire its EV output into the priority-coach card surface so toll/defense-reroute EV actually informs the coaching display.

## Scope
reroute_vs_fight.py + the priority-coach consumer module. Read-only consumption of an existing computed EV, no new autonomous action.

## Accept
The wire is live: the previously-zero-caller symbol now has a real product call site, covered by a test proving the call + effect.

## Proof
Targeted regression + full suite green. live-prove: n/a unless the WO note says otherwise.
