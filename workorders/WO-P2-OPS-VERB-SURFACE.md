# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **slice B DONE** pending Accept · tip base `88b16ac`
> Seat: `impl-aiclient-cursor` · execute slices grow one WO at a time
> Refs: hub banked gap after WO-P0-TW-SHIM · `canon/architecture/cli-verbs.md`

## Goal

Truth-align README with live `./tw --help`, inventory daemon/protocol vs CLI, and
stage ordered execute slices to grow the verb table one WO at a time.

## Live surface (post slice B)

### CLI (`tw2002_aiclient/session/cli.py`)

| Verb | Live? | Notes |
|------|-------|-------|
| `status` | **YES** | `cmd_status` · daemon status JSON |
| `ensure` | **YES** | `cmd_ensure` · spawn+login · adapters path |
| `screen` | **YES** | `cmd_screen` · WO-P2-OPS-VERB-A |
| `stop` | **YES** | `cmd_stop` · WO-P2-OPS-VERB-A |
| `do` | **YES** | `cmd_do` · WO-P2-OPS-VERB-B · settle + control_lock |
| `send` | **YES** | `cmd_send` · WO-P2-OPS-VERB-B · no settle |
| `read` | **YES** | `cmd_read` · WO-P2-OPS-VERB-B · settle, never sends |

`./tw --help` subparsers: `{status,ensure,screen,stop,do,send,read}`.

### Protocol (`session/protocol.py` dispatch)

| Verb | Daemon handles? | CLI wired? |
|------|-----------------|------------|
| `status` | YES | YES |
| `ensure` | YES | YES |
| `screen` | YES | YES (slice A) |
| `stop` | YES | YES (slice A) |
| `do` | YES | YES (slice B) |
| `send` | YES | YES (slice B) |
| `read` | YES | YES (slice B) |

Other aspirational README verbs (`state`, `history`, `watch`, `start`, `spectate`,
`attach`, `menumap`, `loops`, `autoloop`, `aiclient`) are **not** on the greenfield
CLI and must not be advertised as shipped.

## Honesty

README Product/ops + Quickstart + Verb reference track the shipped set; Coming
points here for remaining slices.

## Recommended execute slices

| Slice | Verbs | Depends | Proof sketch |
|-------|-------|---------|--------------|
| **A** | `screen` · `stop` | protocol already present | **DONE** |
| **B** | `do` · `send` · `read` | settle · control_lock | **DONE** — `tests/test_cli_ops_verb_b.py` |
| **C** | `state` · `history` | state_parser / history ring | JSON schema · redaction |
| **D** | `start` (explicit spawn) | env/run-dir | overlap with ensure — maybe docs-only |
| **E** | `watch` | watch hub port | event stream |
| **F** | `spectate` · `attach` | Fable TUI / control_lock | Layer-B pty · never scoop CC mid-chrome |
| **G** | `menumap` · `loops` · `autoloop` | later engines | after world/priority ports |

**Accept for a wire slice:** verb on `./tw --help` · unit/FakeSession proof · path-leak ·
README row moves from Coming → Verb reference in the same commit · **full suite green**.

## Out of scope (honesty / inventory WO)

Implementing any missing verb · touching `screens.py` / `cockpit/**`.
