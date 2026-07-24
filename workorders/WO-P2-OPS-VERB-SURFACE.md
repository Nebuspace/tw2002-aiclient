# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **slice D DONE (docs-only)** pending Accept · tip `82b4094`
> Seat: `impl-aiclient-cursor`
> Refs: hub banked gap after WO-P0-TW-SHIM · `canon/architecture/cli-verbs.md`

## Goal

Truth-align README with live `./tw --help`, inventory daemon/protocol vs CLI, and
stage ordered execute slices to grow the verb table one WO at a time.

## Live surface (post slice D / docs)

### CLI (`tw2002_aiclient/session/cli.py`)

| Verb | Live? | Notes |
|------|-------|-------|
| `status` | **YES** | |
| `ensure` | **YES** | spawn-if-needed + login (`ensure_raw`) |
| `screen` / `stop` | **YES** | slice A |
| `do` / `send` / `read` | **YES** | slice B |
| `history` | **YES** | slice C |
| `start` | **NO** | **slice D docs-only** — see rationale below |
| `state` | **NO** | deferred — `state_parser` not ported |

`./tw --help` subparsers: `{status,ensure,screen,stop,do,send,read,history}`.

### Slice D rationale (`tw start`)

Canon lists `start` as spawn + first settled screen (no login). Archive
`cmd_start` was **CLI-only** (spawn subprocess → `status`/`screen` or `read`) —
there was never a protocol `start` verb. Greenfield `ensure_raw` already embeds
that spawn + post-spawn capped `read` before the `ensure` round trip. Wiring a
second spawn path risks scooping/diverging from `ensure` without a clear
additive caller need (login-free host/port cold connect is rare vs profile
`ensure`). **Decision:** keep `start` off `./tw --help`; document that cold
start = `tw ensure --profile …`. Revisit only if a FakeSession-proven thin
spawn CLI is requested with a concrete non-ensure caller.

## Recommended execute slices

| Slice | Verbs | Status |
|-------|-------|--------|
| **A** | `screen` · `stop` | **DONE** |
| **B** | `do` · `send` · `read` | **DONE** |
| **C** | `history` · (`state` deferred) | **history DONE** · state banked |
| **D** | `start` | **DONE (docs-only)** |
| **E–G** | watch / spectate·attach / menumap… | queued |

**Accept for a docs slice:** README + WO honesty · no fake verb on help · STATUS
disclosure. **Accept for a wire slice:** verb on help · FakeSession · path-leak ·
full suite green.
