# WO-HUB-CLEANUP-SEAT-REFUSE

**Goal:** `scripts/hub-wo-merge-cleanup.sh` reaps **only** hub-owned worktrees (allowlist). Everything else is REFUSE (explicit argv) or SKIP (auto-discover).

**Accept:**
1. Allowlist only: basename `hub-*` under `.worktrees/` or legacy `/private/tmp/hub-*` (and `/tmp/hub-*`).
2. Explicit non-hub path → exit non-zero REFUSE.
3. Auto-discover non-hub → SKIP (do not remove).
4. Falsify both halves: fabricated `cc-scratch` refuses; fabricated `hub-scratch` reaps (then restore).
5. live-prove `n/a`.

**Refs:** CC 21:05:04Z allowlist design · incidents after #195/#197.
