# WO-P1-016 — Hand-off to cockpit

> Status: DONE — hub-Accepted 1d5dacb (2026-07-24)
**Phase:** 1 · **Type:** verify · **Depends:** WO-P1-010
**Canon:** `canon/surfaces/entry-and-profile-selection.md` (Hand-off to the cockpit)

**Goal:** Prove the one-directional launcher→cockpit transition — selecting (or Entering) a profile
row binds it and opens the play shell; Esc from the play shell returns to the launcher, ending the
binding rather than switching worlds under a live connection.

**Scope:** `tw2002_aiclient/app.py` (curses router: launcher ↔ play state transition only). No
cockpit chrome, no daemon wire — a placeholder play screen is sufficient for this WO.

**Accept:**
- Selecting a profile row and pressing Enter transitions to a play-shell screen (placeholder
  content acceptable) with the selected profile's identity visible somewhere on it.
- Esc from the play shell returns cleanly to the launcher list.
- Re-entering the launcher does not carry over any transient play-shell state — the transition is a
  clean close, not a suspend.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient
# select a row, Enter -> play shell shows the profile's identity
# Esc -> back to launcher list, cleanly
```
