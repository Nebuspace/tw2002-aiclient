# WO-FIX-LOGIN-ALIAS-PROMPT-UNHANDLED

**Goal:** Classify TWGS "What Alias do you want to use?" during registration
and answer with a bounded handle+suffix mint (not `automaton_stuck`),
persisting the accepted/attempted alias for the operator.

**Scope:**
- `tw2002_aiclient/session/classify.py` — `login_alias` gate anchor
- `tw2002_aiclient/session/login.py` — decide + `_fresh_alias` + retries
- `tw2002_aiclient/session/protocol.py` — merge `in_game_alias` into secrets
- tests + this WO

**Policy:** max 6 alias attempts; suffix length 3; max alias length 20;
persist non-secret `in_game_alias` in `secrets.json` entry (merge, do not
clobber password).

## Accept

1. Alias collision no longer yields `automaton_stuck` — named mint + send.
2. Alias recorded as `in_game_alias` in secrets entry when saver wired.
3. Unit pins against captured transcript text.
4. Exhausted retries → `alias_retries_exhausted` (bounded).

## Proof

Offline: `tests/test_login_alias_prompt.py`. Live: `tw ensure` on a dialect
that demands Alias completes or fails with the named retry error.

## Refs

Design brief: `audit/design-briefs/wo-fix-login-alias-prompt-unhandled.md`
Live: `a_net_online` / `scout_anet` 2026-08-07.
