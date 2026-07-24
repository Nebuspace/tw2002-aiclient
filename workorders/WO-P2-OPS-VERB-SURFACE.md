# WO-P2-OPS-VERB-SURFACE — Ops CLI verb inventory + wire plan

> Status: **PREP / honesty** 2026-07-24 · tip `914a0a1`
> Seat: `impl-aiclient-cursor` · docs + inventory (no verb implement in this WO)
> Refs: hub banked gap after WO-P0-TW-SHIM · `canon/architecture/cli-verbs.md`

## Goal

Truth-align README with live `./tw --help`, inventory daemon/protocol vs CLI, and
stage ordered execute slices to grow the verb table one WO at a time.

## Live surface (tip `914a0a1`)

### CLI (`tw2002_aiclient/session/cli.py`)

| Verb | Live? | Notes |
|------|-------|-------|
| `status` | **YES** | `cmd_status` · daemon status JSON |
| `ensure` | **YES** | `cmd_ensure` · spawn+login · adapters path |

`./tw --help` subparsers: `{status,ensure}` only.

### Protocol (`session/protocol.py` dispatch)

| Verb | Daemon handles? | CLI wired? |
|------|-----------------|------------|
| `status` | YES | YES |
| `ensure` | YES | YES |
| `screen` | YES | **NO** |
| `stop` | YES | **NO** |

Other aspirational README verbs (`do`, `send`, `read`, `state`, `history`, `watch`,
`start`, `spectate`, `attach`, `menumap`, `loops`, `autoloop`, `aiclient`) are **not**
on the greenfield CLI and must not be advertised as shipped.

## Honesty (this WO)

README Product/ops + Quickstart + Verb reference trimmed to **shipped-only**, with a
short **Coming** note pointing here for the wire queue.

## Recommended execute slices (next WOs — not this one)

| Slice | Verbs | Depends | Proof sketch |
|-------|-------|---------|--------------|
| **A** | `screen` · `stop` | protocol already present | `./tw screen` / `./tw stop` · FakeSession / isolated run-dir |
| **B** | `do` · `send` · `read` | settle (`wait_prompt`) · control_lock | case-sensitive wait · TOCTOU |
| **C** | `state` · `history` | state_parser / history ring | JSON schema · redaction |
| **D** | `start` (explicit spawn) | env/run-dir | overlap with ensure — maybe docs-only |
| **E** | `watch` | watch hub port | event stream |
| **F** | `spectate` · `attach` | Fable TUI / control_lock | Layer-B pty · never scoop CC mid-chrome |
| **G** | `menumap` · `loops` · `autoloop` | later engines | after world/priority ports |

**Accept for a wire slice:** verb on `./tw --help` · unit/FakeSession proof · path-leak ·
README row moves from Coming → Verb reference in the same commit.

## Out of scope (this WO)

Implementing any missing verb · touching `screens.py` / `cockpit/**`.
