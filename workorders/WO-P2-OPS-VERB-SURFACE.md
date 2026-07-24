# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **slice E DONE (docs-only)** pending Accept · tip `135ee38`
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
| `watch` | **NO** | **slice E docs-only** — see rationale |
| `state` | **NO** | deferred — `state_parser` not ported |

`./tw --help` subparsers: `{status,ensure,screen,stop,do,send,read,history}`.

### Slice E rationale (`tw watch`)

Canon: settle-edge push-stream via `WatchHub` (`canon/surfaces/spectate-and-attach.md`).
Archive has `twclient/watch.py` (~113 LOC) + daemon `_handle_subscribe` lifetime
stream + CLI `cmd_watch` NDJSON tail. Greenfield tip (`daemon.py` header):
`WatchHub` / `watch.py` / `subscribe` **explicitly cut** until that module lands —
no `watch.py` under `tw2002_aiclient/session/`. Wiring a real `tw watch` is a
**multi-file substrate WO** (`watch.py` + daemon hub start/stop + subscribe
handler + protocol/status `subscribers` + CLI stream), not a thin CLI add.
**Decision (slice-D honesty bar):** keep `watch` off `./tw --help`; do not invent
a fake one-shot/non-streaming verb. Bank a follow-on **WatchHub port** WO before
CLI wire (feeds slice F spectate too).

## Recommended execute slices

| Slice | Verbs | Status |
|-------|-------|--------|
| **A** | `screen` · `stop` | **DONE** |
| **B** | `do` · `send` · `read` | **DONE** |
| **C** | `history` · (`state` deferred) | **history DONE** · state banked |
| **D** | `start` | **DONE (docs-only)** |
| **E** | `watch` | **DONE (docs-only)** · WatchHub substrate banked |
| **F–G** | spectate·attach / menumap… | queued (F needs WatchHub) |

**Accept for a docs slice:** README + WO honesty · no fake verb on help · STATUS
disclosure. **Accept for a wire slice:** verb on help · FakeSession · path-leak ·
full suite green.
