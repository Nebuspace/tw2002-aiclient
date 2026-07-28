# WO-HUB-CLEANUP-SEAT-REFUSE

**Goal:** Make `scripts/hub-wo-merge-cleanup.sh` refuse seat-owned worktrees (`cc-*`, `.claude/worktrees/*`) so auto-discover cannot violate owning-seat-reaps.

**Accept:** explicit argv of a seat path exits non-zero with REFUSE; auto-discover skips with SKIP line; hub `.worktrees/hub-*` still reaped.

**Refs:** CC PROCESS-NOTE · incidents `cc-*` auto-reap after #195 / #197.
