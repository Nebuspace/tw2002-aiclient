# WO-LIVE-PROVE-DESC-TRUNCATE — Truncate live-prove description to ≤140 chars

**Status:** DONE · PR #53 · origin `40881e3` (was IN PROGRESS · Cursor · WAVE-POST-SPRINT Lane A)
**Posted:** 2026-07-26
**Seat:** Cursor

## Goal

`scripts/hub-live-prove-check.sh` must truncate the Commit Status `description` field to ≤140
characters before posting to the GitHub Statuses API.  The hub hit HTTP 422 when a summary
string exceeded GitHub's limit — the call fails silently or hard, leaving the live-prove gate
stuck.

## Scope

- `scripts/hub-live-prove-check.sh` — truncation logic only (no other changes)

## Constraints

- Must not truncate a description that is ≤140 chars (idempotent on short strings)
- Do not change the script's exit codes, argument parsing, or curl invocation shape
- No new dependencies

## Accept

1. A description string >140 chars is truncated to ≤140 before the API call (assert with a
   shell test or `printf | wc -c` pin in the script or a companion `test_live_prove_truncate.sh`).
2. A description string ≤140 chars passes through unchanged.
3. `bash -n scripts/hub-live-prove-check.sh` exits 0.

## Proof

Shell assert / pin test: `printf '%s' "$TRUNCATED" | wc -c` returns ≤140.  Live: hub runs the
script against a test SHA with a long summary and the API call succeeds (HTTP 201).
