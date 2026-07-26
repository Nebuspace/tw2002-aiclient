# WO-TWD-PROFILE-STORE-UNREADABLE

**Status:** DONE · origin `c263f16`  
**Posted:** 2026-07-25 — CC incident outcome item 9

## Goal

`twd` must not traceback-exit when `config/` or `profiles.toml` is unreadable and no `--host/--port` is given. Emit an actionable error (rc≠0) instead.

## Context

`daemon.py` catches `env.EnvResolutionError`, but `ProfileStoreUnreadable` is **not** a subclass → escapes to full traceback. Design: enumerate the **closed** absent set (`ProfileConnectionError` family — "Absence is never one of these"); catch the **base** for the loud open set so future members default to loud.

## Scope

`daemon.py` / `env.py` catch hierarchy + subclass-walking tripwire test. Live repro: `chmod 000` profiles.toml → no traceback.

## Constraints

Secrets Max-gate orthogonal · no classify · cite AP/env patterns if relevant.

## Accept

Unreadable profiles store → printed actionable error, exit 1, **no** unhandled traceback. Tripwire test fails if a new loud error is wrongly subclassed under absence.

## Proof

Targeted pytest + manual chmod repro in STATUS.

## Refs

CC INCIDENT OUTCOME @ 2026-07-25T22:19:20Z item 3.
