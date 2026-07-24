# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **G-PREP DONE** pending Accept · tip `582c210`
> Seat: `impl-aiclient-cursor`
> Refs: · `WO-P2-OPS-VERB-F-PREP.md` · `WO-P2-OPS-VERB-G-PREP.md`
> HOLD: F2 spectate until Max re-opens CC

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
| **F1** | thin `tw attach` CLI | **DONE** |
| **F1b** | attach secret redaction proofs | **DONE** (ledger sink banked) |
| **F2a/b** | spectate_layout → spectate_app + `tw spectate` | **HOLD** — Max re-opens CC·Fable |
| **G-PREP** | menumap / loops inventory | **DONE** — see `WO-P2-OPS-VERB-G-PREP.md` |
| **G0** | menu_* pure (sig/nav/map_view) | **DONE** |
| **G1** | `tw menumap` CLI | **DONE** |
| **G2–G4** | crawler · loops · autoloop | queued |

**Accept for a wire slice:** verb on help · FakeSession · path-leak · full suite green.
