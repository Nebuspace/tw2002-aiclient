# WO-STATUS-JSON-PROMPT-C21

**Status:** OPEN · Claude Code preferred (secrets-adjacent · follows MT-07)  
**Posted:** 2026-07-26 · DECISIONS §C.2.1

## Goal

Split `tw status` prompt dual-use: live HUD may paint the prompt line; `--json` / structured export must omit or redact credential-shaped / secret-prompt content (classification stays).

## Scope

- `status` response builder / protocol dispatch path that sets `"prompt"`
- Pins: JSON path withholds; live-paint path still shows (or separate field) · secret-prompt heuristic
- One-line stamp in `canon/doctrine/secrets-and-credentials.md` that ensure family is closed and status JSON is the remaining member

## Constraints

- §C.2.1 in `DECISIONS.md` — do not re-litigate
- Do not break cockpit HUD honesty
- No new deps

## Accept

`--json` cannot carry echoed credential/secret-prompt; HUD/live paint still usable; doctrine one-liner; suite green.

## Proof

STATUS + SHA · targeted pytest both directions.

## Refs

CC MT-07/X2 STATUS 2026-07-26T04:05:57Z · §C.2 / §C.2.1
