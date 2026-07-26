# WO-CLASSIFY-CHAIN-LOADBEARING-NOTE

**Status:** OPEN · READY · offline · Claude Code preferred  
**Posted:** 2026-07-26 · CC post-#38 STATUS (dependency chain)

## Goal

Add one durable audit note that C-06 / C-02 / C-01 / PASSWORD-LENGTH-UNKNOWN are **load-bearing for each other**, so a future "simplify NEVER_AUTO_ACTION_CLASSES" or money_prompt narrow cannot silently reopen the credential-leak shape.

## Scope

- `audit/session-classify-audit-coverage-20260726.md` (or short sibling under `audit/`) — one section, not a rewrite
- Optional one-line stamp in `canon/findings.md` if that is the standing index
- **Out:** product code · Explore HOLD · invent new WOs beyond this note

## Accept

1. Note states: post-C-02 password-length chrome lands on `money_prompt` and halts **only because** it is in `NEVER_AUTO_ACTION_CLASSES` (C-06); C-01 guards bare `classify()`; PASSWORD-LENGTH-UNKNOWN re-aims to contract halt.
2. Explicit warning: do not drop/narrow `money_prompt` from NEVER_AUTO without replacing that halt.
3. Doc-only; no product change.

## Proof

STATUS + SHA · path cite · `git show` excerpt.
