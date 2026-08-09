> **2026-08-09:** Tracking Accept satisfied earlier; this WO's *build* Accept (verb LIVE + write-path + tests) is in flight on `wo/BUILD-CLI-VERBS-FRAMES`.

# WO-BUILD-CLI-VERBS-FRAMES-TRACKING

**Status:** BUILDING → see implementation PR (scope+build landed)
**Priority:** MED
**Claimed-by:** impl-aiclient-cursor (tracking only)
**Source:** 6-lens audit 2026-08-09T09:59Z / queue-aiclient.md

## Goal

Keep the TARGET `tw frames {tail,show,grep,diff}` post-mortem verb from silently vanishing
(X6 failure mode). Canon already honestly marks it TARGET — this WO is the durable queue
anchor until a scoped build lands.

## Tip-verify (2026-08-09)

- `canon/architecture/cli-verbs.md:130` — **TARGET — not a `tw` CLI verb yet.**
- Grep on tip: no `cmd_frames` / frames subparser under the product tree (excluding archive).
  `session/cli.py` `--frames N` is the live `tw watch` settle-edge limit, not the post-mortem
  verb. No settle-frame capture write-path to `state/frames/` found in this verify.
- Distinct from the earlier CLI-verbs honesty pass (that only fixed docs falsely claiming
  liveness). This row stays TARGET-on-purpose until built.

## Out of scope (this tracking commit)

Implementing the verb, frame capture write-path, or changing the TARGET label to LIVE.

## Accept (when scheduled to build)

1. `tw frames {tail,show,grep,diff}` registered on the product CLI.
2. Read-only post-mortem over settle frames under `state/frames/` (no daemon required).
3. cli-verbs.md flipped TARGET → LIVE with real flags matching argparse.
4. Pytest coverage for the four subcommands; live-prove n/a (offline frames) unless a
   capture fixture is required.

## Refs

- queue-aiclient.md · WO-BUILD-CLI-VERBS-FRAMES-TRACKING
- canon/architecture/cli-verbs.md (frames TARGET row)
