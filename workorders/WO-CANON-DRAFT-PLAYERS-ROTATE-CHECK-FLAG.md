# WO-CANON-DRAFT-PLAYERS-ROTATE-CHECK-FLAG

**Goal:** Document `tw players rotate --check` (PR #706) in canon — the passive
notify-only surface shipped with zero canon coverage.

**Depends-on:** WO-BUILD-ROTATION-NOTIFY-ONLY-SURFACE (landed #706)

**Scope:**
- `canon/architecture/cli-verbs.md` — players row key-args + one-line effect
- `canon/surfaces/entry-and-profile-selection.md` — rotation-driver paragraph
- this WO file

**Out of scope:** product code; DECISIONS.md Pending update (separate
`WO-CANON-FIX-DECISIONS-STALE-ROTATION-PENDING-ENTRY`).

**Accept:**
1. cli-verbs players row names `--check` and the exit-0 / exit-2 notify contract.
2. entry-and-profile-selection documents `--check` as notify-only (no auto-switch).
3. No product code changes.

**Proof:** `rg -- '--check' canon/` hits both files. Live: n/a (docs-only).
