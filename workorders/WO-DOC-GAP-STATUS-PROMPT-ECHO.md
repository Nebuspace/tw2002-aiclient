# WO-DOC-GAP-STATUS-PROMPT-ECHO — Doc-gap: status-verb prompt-echo secret leak (Mack F7+F8 finding)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · SHA **TBD** (committed alongside or following `WO-P4-050-057-PREP`; Cursor batch)
> Type: docs-only · Phase: 4 · Seat: impl-aiclient-cursor
> Refs: `canon/` secrets-doctrine / findings · `WO-AUDIT-STATUS-WATCH-HONESTY.md`

## Goal
Secrets-doctrine Code-Divergence #1 (canon) names the transcript log file as a secret sink. Mack's PoC on P3-041 proved that `status["prompt"]` receive-echo can leak the **same class of secret** over the live `status` verb — `fake_twgs` never echoes so e2e tests miss it.

This WO is **doc-only**: name the divergence in canon (findings / secrets doctrine / DECISIONS Pending if needed). No code fix in this WO — the code fix is tracked under `WO-AUDIT-STATUS-WATCH-HONESTY.md`.

## Scope
- `canon/` — secrets-doctrine wording: add status-verb prompt-echo as a named leak vector
- `canon/findings.md` — add/update row for prompt-echo risk on status verb
- (Optionally) `DECISIONS.md` Pending entry if a design decision is needed

## Accept
- Status-verb prompt-echo risk is explicitly named in canon
- No code changes in this commit
- STATUS DONE

## Refs
hub HANDOFF @ 21:56:10Z (item B alongside WO-P4-050-057-PREP) · Mack PoC on P3-041 wave · `WO-AUDIT-STATUS-WATCH-HONESTY.md` (code-fix WO)
