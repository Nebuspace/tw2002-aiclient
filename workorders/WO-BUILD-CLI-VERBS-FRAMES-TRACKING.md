# WO-BUILD-CLI-VERBS-FRAMES-TRACKING

**Status:** DONE (PR #642 build + this residual honesty pass)
**Priority:** MED
**Claimed-by:** impl-aiclient-cursor
**Source:** 6-lens audit 2026-08-09T09:59Z / queue-aiclient.md
**Merged build:** PR #642 (`eb8129f` merge; product on `origin/main`)
**Residual close:** cli-verbs.md Implementation-status / daemon-free carve-out still listed
`frames` as TARGET / NOT-a-verb after the catalog row was flipped LIVE — tip-true cleanup.

## Goal

Keep the TARGET `tw frames {tail,show,grep,diff}` post-mortem verb from silently vanishing
(X6 failure mode). Canon already honestly marked it TARGET — this WO was the durable queue
anchor until the scoped build landed, then the residual honesty catch-up.

## Tip-verify (2026-08-09 close)

- Catalog row `cli-verbs.md` frames table: **LIVE** (PR #642).
- Product: `tw2002_aiclient/frames_cli.py` + `session/cli.py` `add_frames_parsers`;
  `FrameRecorder` settle write-path; tests in `tests/test_frame_recorder.py`.
- Residual fixed here: daemon-free LIVE list + Implementation-status "NOT a tw CLI verb"
  no longer contradict the LIVE catalog row.

## Accept

1. `tw frames {tail,show,grep,diff}` registered on the product CLI. — met (#642)
2. Read-only post-mortem over settle frames under `state/frames/` (no daemon required). — met
3. cli-verbs.md flipped TARGET → LIVE with real flags; no leftover TARGET/NOT-verb contradiction. — met
4. Pytest coverage for the four subcommands; live-prove n/a (offline frames). — met (#642)

## Refs

- queue-aiclient.md · WO-BUILD-CLI-VERBS-FRAMES-TRACKING
- workorders/WO-BUILD-CLI-VERBS-FRAMES.md · PR #642
- canon/architecture/cli-verbs.md
