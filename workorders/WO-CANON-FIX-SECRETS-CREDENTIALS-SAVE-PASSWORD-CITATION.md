# WO-CANON-FIX-SECRETS-CREDENTIALS-SAVE-PASSWORD-CITATION

**Status:** IN FLIGHT (impl-aiclient-h1 · audit-refill batch)

## Goal

Correct Citation [1] in `secrets-and-credentials.md`: `credentials.py` is read-only
for passwords; atomic chmod-600 write lives in `protocol.py` (`_merge_secret_entry` /
`_save_password`).

## Scope

- `canon/doctrine/secrets-and-credentials.md` — Citations [1] / [1b]
- This WO

## Out of scope

Consolidating the write into `credentials.py` (tech debt named, not this WO).

## Accept

Citation names the real write module; does not claim `credentials.save_password()`.

## Proof

Docs-only · live-prove **n/a**
