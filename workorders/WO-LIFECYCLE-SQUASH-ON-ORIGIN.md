# WO-LIFECYCLE-SQUASH-ON-ORIGIN — "tip on origin" ≠ ancestry under squash merges

**Status:** PARTIAL · cleanup script carve-out in this PR · Nebuspace CLAUDE.md prose still owed  
**Posted:** 2026-07-27T20:27:00Z · hub from CC STATUS after #114 reap  
**Seat:** hub / orchestrator (protocol authoring) — CC may review; HOLD seats do not invent  
**Depends:** none  
**Refs:** CC 2026-07-27T20:26:30Z · throwaway-worktree lifecycle (Proposed 2026-07-25) · `hub-wo-merge-cleanup.sh` REFUSE-on-ancestor

## Goal

Replace the lifecycle / cleanup predicate **"tip is an ancestor of origin/main"** with a test that works under **squash-merge** workflows.

Squash commits have a single parent on main. Pre-squash WO tips are **never** ancestors of `origin/main` after a successful squash — so `git merge-base --is-ancestor <tip> origin/main` false-alarms on every success (#109–#114 pattern).

## Spec

**"Tip is on origin" (squash-safe):** for every path the WO / PR changed,

```text
git rev-parse <pre-squash-tip>:<path> == git rev-parse origin/main:<path>
```

(blob identity). Optionally also require `gh pr view <n> --json state` = `MERGED`.

Ancestry remains valid only for **merge commits** (non-squash) workflows — document both, default to blob identity when the repo squash-merges.

## Scope

- Nebuspace `CLAUDE.md` throwaway-worktree lifecycle wording (and/or `.samantha/references/coordination-protocol/` if that is SoT)
- `tw2002-aiclient/scripts/hub-wo-merge-cleanup.sh` REFUSE message / predicate if it still uses ancestry alone
- This WO stamped DONE when wording + script agree

## Accept

1. Lifecycle text names blob-identity as the squash-safe "on origin" test.
2. Cleanup script does not train seats to ignore false ancestry alarms (or documents squash carve-out).
3. PR + STATUS (hub may self-land).

## Proof

Docs/process; live-prove n/a. Cite CC #114 episode (ancestry warned; blob identity was the real gate).
