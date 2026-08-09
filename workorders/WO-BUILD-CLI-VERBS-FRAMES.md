# WO-BUILD-CLI-VERBS-FRAMES

**Status:** IN FLIGHT (impl-aiclient-cursor)
**Priority:** MED
**Depends-on:** WO-BUILD-CLI-VERBS-FRAMES-TRACKING (tracking Accept satisfied)

## Goal

Land the TARGET `tw frames {tail,show,grep,diff}` post-mortem verb + settle-frame
write-path (`state/frames/<session_id>.jsonl`) per `canon/architecture/cli-verbs.md`
and `canon/engine/trace-ledger.md` Layer 4.

## Scope

- `tw2002_aiclient/frame_recorder.py` — FrameRecorder + read/grep/diff helpers
- `tw2002_aiclient/frames_cli.py` — CLI registration
- `session/protocol.py` `build_response` optional recorder hook
- `session/daemon.py` attach FrameRecorder on session
- `canon/architecture/cli-verbs.md` TARGET → LIVE
- Tests: `tests/test_frame_recorder.py`

## Accept

1. `tw frames {tail,show,grep,diff}` registered on the product CLI.
2. Read-only post-mortem over settle frames under `state/frames/` (no daemon required).
3. cli-verbs.md flipped TARGET → LIVE with real flags matching argparse.
4. Pytest coverage for recorder + CLI; live-prove n/a (offline frames).

## Refs

- queue-aiclient.md · WO-BUILD-CLI-VERBS-FRAMES-TRACKING
- archive `twclient/frame_recorder.py` (port source; gitignored)
