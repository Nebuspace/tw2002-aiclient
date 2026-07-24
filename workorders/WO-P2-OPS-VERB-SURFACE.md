# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **F-PREP DONE** pending Accept · tip `b9dc80d`
> Seat: `impl-aiclient-cursor`
> Refs: hub banked gap · `canon/architecture/cli-verbs.md` ·
> `canon/surfaces/spectate-and-attach.md` · `WO-P2-OPS-VERB-F-PREP.md`

## Goal

Truth-align README with live `./tw --help`, inventory daemon/protocol vs CLI, and
stage ordered execute slices to grow the verb table one WO at a time.

## Live surface (post slice E2)

### CLI (`tw2002_aiclient/session/cli.py`)

| Verb | Live? | Notes |
|------|-------|-------|
| `status` … `history` | **YES** | slices A–C |
| `watch` | **YES** | **E2** · NDJSON/`print_response` tail over daemon `subscribe` · `--frames N` |
| `start` | **NO** | slice D docs-only |
| `state` | **NO** | deferred — `state_parser` not ported |

`./tw --help` subparsers:
`{status,ensure,screen,stop,do,send,read,history,watch}`.

### WatchHub + CLI

**WO-P2-WATCHHUB-PORT:** `watch.py` + daemon `_handle_subscribe` + `status.subscribers`.
**WO-P2-OPS-VERB-E2:** `tw watch` CLI — read-only lifetime stream; Ctrl-C / `--frames`
closes the socket without driving the game.

## Recommended execute slices

| Slice | Verbs | Status |
|-------|-------|--------|
| **A–D** | … | **DONE** (D docs-only) |
| **E** | `watch` honesty | **DONE (docs-only)** |
| **WATCHHUB** | substrate | **DONE** |
| **E2** | `tw watch` CLI | **DONE** |
| **F-PREP** | spectate·attach inventory | **DONE** — see `WO-P2-OPS-VERB-F-PREP.md` |
| **F1** | thin `tw attach` CLI (daemon attach already live) | **DONE** pending Accept |
| **F2a/b** | spectate_layout → spectate_app + `tw spectate` | queued (curses-heavy) |
| **G** | menumap… | queued |

**Accept for a wire slice:** verb on help · FakeSession · path-leak · full suite green.
