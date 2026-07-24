# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **slice C partial** — `history` DONE pending Accept · `state` deferred
> Seat: `impl-aiclient-cursor` · tip base `a9d40bd`
> Refs: hub banked gap after WO-P0-TW-SHIM · `canon/architecture/cli-verbs.md`

## Goal

Truth-align README with live `./tw --help`, inventory daemon/protocol vs CLI, and
stage ordered execute slices to grow the verb table one WO at a time.

## Live surface (post slice C / history)

### CLI (`tw2002_aiclient/session/cli.py`)

| Verb | Live? | Notes |
|------|-------|-------|
| `status` | **YES** | `cmd_status` |
| `ensure` | **YES** | `cmd_ensure` |
| `screen` | **YES** | slice A |
| `stop` | **YES** | slice A |
| `do` / `send` / `read` | **YES** | slice B |
| `history` | **YES** | slice C · session ring · secret args redacted at record time |
| `state` | **NO** | deferred — `state_parser` not ported (~900 LOC archive); no fake skeleton |

`./tw --help` subparsers: `{status,ensure,screen,stop,do,send,read,history}`.

### Protocol

| Verb | Daemon | CLI |
|------|--------|-----|
| …A/B verbs… | YES | YES |
| `history` | YES | YES |
| `state` | NO | NO |

## Recommended execute slices

| Slice | Verbs | Status |
|-------|-------|--------|
| **A** | `screen` · `stop` | **DONE** |
| **B** | `do` · `send` · `read` | **DONE** |
| **C** | `history` · (`state` deferred) | **history DONE** · state banked |
| **D–G** | start / watch / spectate·attach / menumap… | queued |

**Accept for a wire slice:** verb on `./tw --help` · FakeSession proof · path-leak ·
README + allowlist · **full suite green**.
