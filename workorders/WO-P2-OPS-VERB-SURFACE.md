# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **WATCHHUB-PORT DONE** pending Accept · tip `78bb983`
> Seat: `impl-aiclient-cursor`
> Refs: hub banked gap after WO-P0-TW-SHIM · `canon/architecture/cli-verbs.md` ·
> `canon/surfaces/spectate-and-attach.md`

## Goal

Truth-align README with live `./tw --help`, inventory daemon/protocol vs CLI, and
stage ordered execute slices to grow the verb table one WO at a time.

## Live surface (post slice E / docs)

### CLI (`tw2002_aiclient/session/cli.py`)

| Verb | Live? | Notes |
|------|-------|-------|
| `status` … `history` | **YES** | slices A–C |
| `start` | **NO** | slice D docs-only |
| `watch` | **NO CLI** | **WatchHub substrate LIVE** (WO-P2-WATCHHUB-PORT) — daemon `subscribe` streams settle-edge events; `tw watch` CLI = slice E2 |
| `state` | **NO** | deferred — `state_parser` not ported |

`./tw --help` subparsers: `{status,ensure,screen,stop,do,send,read,history}`
(unchanged — no fake `watch` verb).

### Slice E rationale (`tw watch` CLI) + WatchHub port

Canon: settle-edge push-stream via `WatchHub` (`canon/surfaces/spectate-and-attach.md`).
**WO-P2-WATCHHUB-PORT DONE:** `tw2002_aiclient/session/watch.py` + daemon hub
start/stop + `_handle_subscribe` + `status.subscribers`. CLI `tw watch` still
deferred (E2) so `./tw --help` stays honest until the NDJSON tail lands.

## Recommended execute slices

| Slice | Verbs | Status |
|-------|-------|--------|
| **A** | `screen` · `stop` | **DONE** |
| **B** | `do` · `send` · `read` | **DONE** |
| **C** | `history` · (`state` deferred) | **history DONE** · state banked |
| **D** | `start` | **DONE (docs-only)** |
| **E** | `watch` CLI | **docs-only** · substrate via **WATCHHUB-PORT** |
| **E2** | `tw watch` CLI wire | queued (needs WatchHub — now live) |
| **F–G** | spectate·attach / menumap… | queued (F needs WatchHub) |

**Accept for a docs slice:** README + WO honesty · no fake verb on help · STATUS
disclosure. **Accept for a wire slice:** verb on help · FakeSession · path-leak ·
full suite green.
