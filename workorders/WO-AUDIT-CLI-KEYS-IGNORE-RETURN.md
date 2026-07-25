# WO-AUDIT-CLI-KEYS-IGNORE-RETURN — Bank `cli --keys` ignore-return

> Status: **DRAFT** 2026-07-25 · Zone-A micro-bank · MICRO-SCOUT pin tip `01bac96`  
> Type: polish · Priority: P3 · Lens: L4  
> Refs: `session/cli.py:481-486` · `attach_client.send_key` → bool · CC POLISH Zone-A bank

## Scout pin (origin `01bac96`)
`tw attach --keys` path in **`tw2002_aiclient/session/cli.py:481-486`**: after encoding, calls `conn.send_key(data)` (returns `bool` ok/fail at `attach_client.py:72-83`) then **`return 0` unconditionally** — send failure is ignored for process exit status. Flag definition at `cli.py:652-656`.

## Goal
Decide and document whether ignoring `send_key`'s return is intentional — either wire it into exit status / logging, or mark `# noqa` / comment with rationale so it is not a silent lint/smell.

## Scope
- A: `session/cli.py:485-486` (and optional nearby help text)
- B: optional thin test if wiring exit status

## Constraints
No product mode/seat-key invent. Prefer document-or-wire, not silent delete. Tripwire untouched.

## Accept
Either: (1) `send_key` False → non-zero exit / observable ERROR, or (2) explicit comment at `cli.py:485` that ignore→exit-0 is intentional for scripted attach.

## Proof
Diff + optional CLI smoke. Push waits Accept.
