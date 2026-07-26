# WO-CODEQL-ACTIONS-WORKFLOW-PERMS

**Status:** READY FOR HUB COMMIT · Cursor · tip pending push · `wo/CODEQL-ACTIONS-PERMS` · [PR #10](https://github.com/Nebuspace/tw2002-aiclient/pull/10)  
**Posted:** 2026-07-26 · GitHub code scanning alert #1  
**Alert:** https://github.com/Nebuspace/tw2002-aiclient/security/code-scanning/1  
**Rule:** `actions/missing-workflow-permissions` (warning)  
**Path:** `.github/workflows/suite.yml` (~line 32)  
**Likely introduced:** PR-CI suite workflow land (`7dbe09f` / PR #1 era) — scan lagged onto `main`

## Goal

Give the `suite` workflow an explicit least-privilege `permissions` block so CodeQL stops flagging unconstrained `GITHUB_TOKEN`.

## Fix shape

At workflow top-level (or on the `suite` job), add e.g.:

```yaml
permissions:
  contents: read
```

Widen only if a future step needs more (contents: write is not required for checkout+pytest).

## Scope

- `.github/workflows/suite.yml` (+ any sibling workflows that trip the same rule when found)

## Accept

1. Alert #1 dismisses/resolves on next default-branch scan (or is clearly fixed in diff).
2. Offline `suite` workflow still greens on the PR.
3. No secrets / no permission escalation beyond read unless justified in STATUS.

## Proof

```text
gh pr checks <PR>   # suite green
# hub pre-merge sweep should eventually drop #1 from "new"
```

## Refs

- Max/hub protocol: pre-merge code-scanning sweep (lagging indicator; does not block the merge that discovers it)
- `scripts/hub-code-scanning-sweep.sh`
