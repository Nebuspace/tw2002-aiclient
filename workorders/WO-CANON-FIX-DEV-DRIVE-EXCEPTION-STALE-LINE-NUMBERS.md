# WO-CANON-FIX-DEV-DRIVE-EXCEPTION-STALE-LINE-NUMBERS

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Tip-true line citations for `Session._require_dev_sender_authorized()` and its
`send()` / `send_raw()` call sites in `canon/doctrine/dev-drive-exception.md`.

## Accept

Citations match tip `tw2002_aiclient/session/session.py`: def `:936`, `send()`
gate `:962`, `send_raw()` entry `:1006`, gate `:1052`.

## Proof

Docs-only; path-leak scan clean. live-prove: n/a.
