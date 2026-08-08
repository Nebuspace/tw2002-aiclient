# WO-WIRE-MINED-SKILLS-PROMOTE-CLI

**Status:** READY · gated: no
**Posted:** 2026-08-08 · orchestrator HANDOFF (unused-wire tranche 2, background triage)

## Goal
rules/ has approve/promote_draft; skills/loops mined drafts under state/skills/_drafts/ have no equivalent promote path. Add the missing promote step, mirroring rules/'s existing pattern.

## Scope
loops/recorder.py and the skills-drafts module; mirror rules/ promote_draft shape exactly.

## Accept
The wire is live: the previously-zero-caller symbol now has a real product call site, covered by a test proving the call + effect.

## Proof
Targeted regression + full suite green. live-prove: n/a unless the WO note says otherwise.
