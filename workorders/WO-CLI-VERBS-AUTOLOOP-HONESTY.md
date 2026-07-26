# WO-CLI-VERBS-AUTOLOOP-HONESTY

**Status:** **SUPERSEDED** by [`WO-CLI-VERBS-CANON-RECONCILE`](WO-CLI-VERBS-CANON-RECONCILE.md) · docs/canon · banked from X4 STATUS `344991e`  
**Posted:** 2026-07-26T07:24Z · **Superseded:** 2026-07-26

> **Do not work from this file.** Its scope is fully absorbed by the reconcile WO, which additionally
> covers the two `record` divergences and the undocumented wire-only `state` verb.
>
> **One claim below is stale and must not be inherited.** The Goal says `floor` is *"refused as
> `unsupported_arg` until enforced."* That was true at X4 (`344991e`). **X5 landed an hour later and
> `floor` is now genuinely enforced and accepted on the wire** (`ARGS_AUTOLOOP_START = {"name",
> "floor"}`). A lane working from this file would have documented a refusal that no longer exists.
> Banked queues age against a moving tip — that is the reason this banner exists rather than a silent
> delete.

## Goal

Align `cli-verbs.md` (and related doctrine) with shipped X4: three verbs (start/stop/status), `name` only; `cycles`/`floor`/`force`/`param` refused as `unsupported_arg` until enforced; pause/resume deferred until X5 rails.

## Scope

- Canon / doctrine docs only (no product regression to fake four verbs)
- Cross-link X4/X5 Accept pins

## Constraints

- Docs win: update canon to match honest product, do not expand product to match stale ads
- Pause/resume stay out until repetition rails exist

## Accept

Canon matches wire; no advertisement of unenforced flags.

## Proof

STATUS + SHA · quote before/after.

## Refs

CC X4 STATUS · `cli-verbs.md:135` · hub Accept 2026-07-26T06:58:59Z
