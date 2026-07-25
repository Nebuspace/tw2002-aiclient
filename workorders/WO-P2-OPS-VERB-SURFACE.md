# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **G1 DONE** · tip `cbfb1e5` · README sync in flight
> Seat: `impl-aiclient-cursor`
> Refs: · `WO-P2-OPS-VERB-F-PREP.md` · `WO-P2-OPS-VERB-G-PREP.md`
> HOLD: ops `tw spectate` **RETIRED / WONTBUILD** (Max `@ 13:13:55Z`) · **G2 EXECUTING** · G3→G4 staged (Max GO whole sequence `@ 13:15:00Z`)

## Goal

Truth-align README with live `./tw --help`, inventory daemon/protocol vs CLI, and
stage ordered execute slices to grow the verb table one WO at a time.

## Live surface (post G1)

### CLI (`tw2002_aiclient/session/cli.py`)

| Verb | Live? | Notes |
|------|-------|-------|
| `status` … `history` | **YES** | slices A–C |
| `watch` | **YES** | **E2** · NDJSON/`print_response` tail over daemon `subscribe` · `--frames N` |
| `attach` | **YES** | **F1** · thin control-lock forward (no curses) |
| `menumap` | **YES** | **G1** · read-only inspector over G0 menu store |
| `start` | **NO** | slice D docs-only |
| `state` | **NO** | deferred — `state_parser` not ported |
| `spectate` | **NO** | **RETIRED / WONTBUILD** — Max `@ 13:13:55Z`; in-cockpit Spectate LIVE |
| `loops` / `autoloop` | **NO** | **G3–G4 STAGED** behind G2 (HOLD lifted `@ 13:15:00Z`) |

`./tw --help` subparsers:
`{status,ensure,screen,stop,do,send,read,history,watch,attach,menumap}`.

### WatchHub + CLI

**WO-P2-WATCHHUB-PORT:** `watch.py` + daemon `_handle_subscribe` + `status.subscribers`.
**WO-P2-OPS-VERB-E2:** `tw watch` CLI — read-only lifetime stream; Ctrl-C / `--frames`
closes the socket without driving the game.

## Recommended execute slices

| Slice | Verbs | Status | File |
|-------|-------|--------|------|
| **A** | `tw screen` · `tw stop` | **DONE** | [WO-P2-OPS-VERB-A.md](WO-P2-OPS-VERB-A.md) |
| **B** | `tw do` · `tw send` · `tw read` | **DONE** | [WO-P2-OPS-VERB-B.md](WO-P2-OPS-VERB-B.md) |
| **C** | `tw history` | **DONE** | [WO-P2-OPS-VERB-C.md](WO-P2-OPS-VERB-C.md) |
| **D** | `tw start` (docs-only) | **DONE (docs-only)** | [WO-P2-OPS-VERB-D.md](WO-P2-OPS-VERB-D.md) |
| **E** | `tw watch` honesty (docs-only) | **DONE (docs-only)** | [WO-P2-OPS-VERB-E.md](WO-P2-OPS-VERB-E.md) |
| **WATCHHUB** | substrate (WatchHub port) | **DONE** | [WO-P2-WATCHHUB-PORT.md](WO-P2-WATCHHUB-PORT.md) |
| **E2** | `tw watch` CLI (NDJSON tail) | **DONE** | [WO-P2-OPS-VERB-E2.md](WO-P2-OPS-VERB-E2.md) |
| **F-PREP** | spectate·attach inventory | **DONE** | [WO-P2-OPS-VERB-F-PREP.md](WO-P2-OPS-VERB-F-PREP.md) |
| **F1** | thin `tw attach` CLI | **DONE** | [WO-P2-OPS-VERB-F1.md](WO-P2-OPS-VERB-F1.md) |
| **F1b** | attach secret redaction proofs | **DONE** (ledger sink banked) | [WO-P2-OPS-VERB-F1b.md](WO-P2-OPS-VERB-F1b.md) |
| **F2a/b** | spectate_layout → spectate_app + `tw spectate` | **RETIRED / WONTBUILD** — Max `@ 13:13:55Z`; cockpit Spectate LIVE | — |
| **G-PREP** | menumap / loops inventory | **DONE** | [WO-P2-OPS-VERB-G-PREP.md](WO-P2-OPS-VERB-G-PREP.md) |
| **G0** | menu_* pure (sig/nav/map_view) | **DONE** | [WO-P2-OPS-VERB-G0.md](WO-P2-OPS-VERB-G0.md) |
| **G1** | `tw menumap` CLI | **DONE** | [WO-P2-OPS-VERB-G1.md](WO-P2-OPS-VERB-G1.md) |
| **G2** | menu dialogue-graph crawler | **DONE** | [WO-P2-G2-MENU-CRAWLER.md](WO-P2-G2-MENU-CRAWLER.md) |
| **G3** | `tw loops` list | **IN FLIGHT** | [WO-P2-G3-LOOPS.md](WO-P2-G3-LOOPS.md) |

**Accept for a wire slice:** verb on help · FakeSession · path-leak · full suite green.
