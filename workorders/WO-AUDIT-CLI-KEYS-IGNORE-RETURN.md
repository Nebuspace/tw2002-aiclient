# WO-AUDIT-CLI-KEYS-IGNORE-RETURN — Bank `cli --keys` ignore-return

> Status: **DRAFT** 2026-07-25 · Zone-A micro-bank · tip `00cb9e8`  
> Type: polish · Priority: P3 · Lens: L4  
> Refs: CC POLISH Zone-A bank · hub optional micro list

## Goal
Decide and document whether `cli --keys` (or equivalent) intentionally ignores a return value — either wire the return into exit status / logging, or mark `# noqa` / comment with rationale so it is not a silent lint/smell.

## Scope
- A: `tw` / CLI keys path (confirm file:line at execute)
- B: optional thin test if wiring exit status

## Constraints
No product mode/seat-key invent. Prefer document-or-wire, not silent delete. Tripwire untouched.

## Accept
Either: (1) return value drives exit/log observably, or (2) explicit comment + bank note that ignore is intentional.

## Proof
Diff + optional CLI smoke. Push waits Accept.
