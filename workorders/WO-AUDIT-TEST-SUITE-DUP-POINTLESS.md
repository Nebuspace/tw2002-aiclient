# WO-AUDIT-TEST-SUITE-DUP-POINTLESS — Pytest suite duplicate / pointless test audit (read-only report)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **DONE** · report on main `5704a47` (`workorders/AUDIT-TEST-SUITE-DUP-POINTLESS.md`) (was IN FLIGHT 2026-07-25 · dispatched to Cursor @ 14:24:58Z (Max-requested NOW))
> Type: docs/audit · Priority: P0 (Max direct) · Lens: L4 cleanup / L5 doc-gap
> Refs: `canon/testing/test-case-catalog.md` · `pytest.ini` ignore list · OKF catalog `4882045`

## Goal
Examine the pytest suite for **duplicate** or **pointless** test cases; deliver a hub-triage report — **no deletions, no consolidations, no pytest.ini changes** in this WO.

## Scope (read-only / docs-report only)
- `tests/**/*.py` (active + BANKED/`--ignore` — mark status)
- `canon/testing/test-case-catalog.md` + `canon/testing/cases/` as inventory map
- Optional: `pytest --collect-only` for collectable set cross-check
- Output report: `workorders/AUDIT-TEST-SUITE-DUP-POINTLESS.md` or `canon/testing/`

## Constraints
- Read-only: **no** product `.py` edits, **no** mass deletes, **no** `pytest.ini` changes in this WO
- Do NOT re-derive CC evidence — incorporate CC pre-classification (provided by hub @ 14:26:12Z)
- Do NOT cut: `test_cli_attach_keys_exit_code.py` (honesty pin); `test_spectate_no_send.py` (security canary); crawl_sacrificial refuse family; redaction + control-lock pins

## What to hunt
1. **Duplicates** — same assertion under different names; copy-paste twins; parametrize-able clones
2. **Pointless** — asserts only that code exists/imports; tautologies; cannot-fail tests; obsolete pins of retired behavior
3. **Near-duplicates** — keep if different failure mode; say so explicitly

## Accept
1. Report committed + STATUS cites path+SHA
2. Zero product behavior change
3. Push waits Accept; hub can triage CUT/MERGE without re-deriving evidence

## Proof
Report file present; hub can open + review recommendations without re-running the analysis.

## Refs
Max @ 10:24 ET · CC pre-classification evidence relay @ 14:26:12Z · hub HANDOFF @ 14:24:58Z
