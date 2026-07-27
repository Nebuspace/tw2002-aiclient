# WO-AUDIT-CLI-ENCODE-SURROGATE-ASCII — CLI --keys surrogate / unencodable byte encoding honesty

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **DONE** · origin `fec3ffe` (was IN FLIGHT 2026-07-25 · dispatched @ 14:21:28Z (isolated worktree) · F3 / WO-AUDIT-KEYS-ENCODE-HONESTY folded in)
> Type: harden · Priority: P0 · Lens: L2 code-vs-canon / encoding honesty
> Refs: `tw2002_aiclient/session/cli.py` `--keys` path · F3 session-audit finding · `canon/architecture/secrets-and-credentials.md`

## Goal
Honour the `--keys` encoding contract on the CLI path: unencodable / surrogate bytes (`\udcxx`) must be **refused at the wire boundary** (not silently delivered). The false "refused client-side before the wire" comment in `daemon.py` (a D3 sub-finding) folds into the daemon lane (SURROGATE-ASCII owns `cli.py` only; daemon comment = daemon lane). WO-AUDIT-KEYS-ENCODE-HONESTY (F3 session-audit finding) is folded into this dispatch.

## Scope
- `tw2002_aiclient/session/cli.py` — `--keys` encode path (surrogate/unencodable byte refusal)
- `tests/test_cli_*.py` — encode-honesty pins; `--keys ""` empty → rc 0 pin preserved (honesty pin for SURROGATE/D3)
- Optional: thin test helper for encoding probe

## Constraints
- `cli.py` lane; do NOT touch `daemon.py` (separate lane owned by F5-A→socket)
- False `daemon.py` comment (D3) folds into daemon lane — NOT this WO
- `--keys ""` → rc 0 pin must be PRESERVED (not cut — makes SURROGATE/D3 fix provable)
- Full suite green; path-leak

## Accept
1. Unencodable / surrogate `--keys` bytes refused at CLI boundary (not silently delivered to wire)
2. `--keys ""` → rc 0 preserved
3. `daemon.py` untouched
4. Full suite green

## Proof
Isolated cert + encode-probe red→green + STATUS with SHA.

## Refs
CC STATUS @ 14:21:28Z · session-audit Lane C (F3 WO-AUDIT-KEYS-ENCODE-HONESTY folded in) · hub HANDOFF wave @ 13:29:19Z · `cli.py --keys` argv doctrine gap noted
