# WO-MT-12-WATCH-DOCSTRING

**Status:** OPEN · Cursor  
**Posted:** 2026-07-25T20:04:13Z

## Goal

Fix `cli.py` module docstring claiming `tw watch` is sole lifetime-stream exception (attach also holds a socket).

## Scope

`tw2002_aiclient/cli.py` docstring only.

## Accept

Docstring matches reality; no behavior change (AST identity except docstring).

## Proof

STATUS SHA.

## Refs

- `workorders/AUDIT-MISSING-TESTS.md` MT-12
