# WO-CLEANUP-REPLAYSESSION-PROTOCOL-UNUSED

**Status:** IN FLIGHT (this PR)
**Queue:** queue-aiclient.md product batch 476-490 (row 490)
**Answers:** audit claim that `ReplaySession` Protocol is exported but never used as a type.

## Goal

Wire `ReplaySession` into a real call signature so the Protocol is load-bearing, not docstring-only.

## Verify-first

On tip `origin/main` @ 6c3f9cf6: `class ReplaySession(Protocol)` at `loops/player.py:578` is exported and cited in docs/docstrings; `replay_loop(loop, session, …)` left `session` untyped. Structural duck adapters (`session/autoloop.py` `_ReplayPort`, test fakes) already satisfy the Protocol methods.

## Change

Annotate `replay_loop(..., session: ReplaySession, ...)`.

## Accept

- Annotation present; pytest subset for loop player green.
- No behavior change.
