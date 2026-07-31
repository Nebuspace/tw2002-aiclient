# WO-STAMP-CERT-JUNIT-DONE

**Goal:** Paper-close `WO-CERT-JUNIT-HARDFAIL` — product already on `main`
(`scripts/junitxml_guard.py` + `scripts/test_junitxml_guard.sh`, PR #130
`ab8fc5f`). Banner still says IN PROGRESS; QUEUE row still READY/stale.

## Scope

- `workorders/WO-CERT-JUNIT-HARDFAIL.md` — Status → **DONE** · cite #130 /
  `ab8fc5f` (or current tip that contains the guard)
- Optional: one-line note in `.samantha/coord/QUEUE.md` if that SSOT still
  lists it as READY (hub path under Nebuspace — only if this seat can edit
  it; otherwise leave QUEUE to hub)

## Constraints

- Docs / stamp only — **no** product code
- Tip-check first: `scripts/junitxml_guard.py` exists and
  `scripts/test_junitxml_guard.sh` pins missing/empty/zero-tests

## Accept

1. WO banner Status is DONE with PR/SHA cite.
2. Tip-check evidence in STATUS (paths + one guard message string).

## Proof

- `bash scripts/test_junitxml_guard.sh` exit 0 (or cite already-green on tip)
- live-prove **n/a** (docs stamp)

## Refs

- PR #130 · `ab8fc5f`
- `scripts/junitxml_guard.py` · `scripts/ci_skip_count_guard.py` (CI sibling)
