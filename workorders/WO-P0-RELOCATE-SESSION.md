# WO-P0-RELOCATE-SESSION — Relocate session module to one-tree layout (ADR-001)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`4080a37`** (Cursor · ADR-001 Accepted)
> Type: build · Phase: 0 · Seat: impl-aiclient-cursor
> Refs: `canon/ADR/001-one-tree-embedded-session.md` · `tw2002_aiclient/` package

## Goal
Relocate session layer into the one-tree `tw2002_aiclient` package (as mandated by ADR-001 Accepted). Ensure `python -m tw2002_aiclient` works; `cli --help` exits 0; TTY gate exits 2 on non-TTY; `get_password` env/absent paths work.

## Scope
- `tw2002_aiclient/` package restructure — session into one tree
- `pyproject.toml` package config
- `cli.py` entry point

## Outcome
One-tree relocate works. Hub independent verify ✅ — import session/credentials · cli --help 0 · TTY gate 2 · get_password env/absent ✅. SHA `4080a37`.

## Refs
hub HANDOFF @ 00:23:52Z · CC STATUS DONE + PUSHED @ 00:24:28Z + hub verify ✅ `4080a37`
