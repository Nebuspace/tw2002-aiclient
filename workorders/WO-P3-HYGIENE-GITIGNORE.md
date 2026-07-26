# WO-P3-HYGIENE-GITIGNORE — Stop public scoop of local trees

> Status: **DONE** · origin `1fd316b` (hub Accept stamp 2026-07-26 · was EXECUTE DONE awaiting Accept)
> Seat: `impl-aiclient-cursor` · docs/gitignore only
> Ruling: orchestrator @ 2026-07-24T10:36:48Z — **(a) gitignore archive — mandatory**

## Goal

Prevent accidental `git add` of untracked local/reference trees — especially
`archive/` (secrets-adjacent) — into this public repo.

## Shipped

`.gitignore` additions: `archive/` · `workorders/drafts/` · `.samantha-coord` ·
`.samantha-identity` · `*.code-workspace` · `.cursor/rules/` · `.cursor/sandbox.json`

**Not committed:** anything under `archive/` (or the other ignored paths).

## Proof

```bash
git check-ignore -v archive/pre-rebirth-2026-07-23/config/config/secrets.json
# expect: .gitignore:archive/ …
git status -u --short | grep -E 'archive/|drafts/|\.samantha-coord|code-workspace' || true
# expect: no ?? lines for those
```
