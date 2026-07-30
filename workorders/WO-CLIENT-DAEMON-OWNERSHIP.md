# WO-CLIENT-DAEMON-OWNERSHIP

**Goal:** Make the daemon an app-owned implementation detail: launcher shows the one active profile ONLINE, and whole-app quit offers a default-No confirm to stop that profile’s daemon session. Preserve Esc→launcher continuity.

**Scope:**
- `canon/ADR/001-one-tree-embedded-session.md`
- `canon/surfaces/entry-and-profile-selection.md`
- `canon/surfaces/trainer-cockpit.md`
- `canon/surfaces/mode-line-and-teach-controls.md`
- `tw2002_aiclient/daemon_lifecycle.py` (new)
- `tw2002_aiclient/screens.py` (ProfileRow.online + launcher ONLINE column)
- `tw2002_aiclient/app.py` (presence refresh + quit confirm)
- `tests/test_daemon_lifecycle.py`, `tests/test_daemon_lifecycle_pty.py`
- `tests/test_play_chrome_nav.py` (quit → Enter for confirm-safe teardown)

**Constraints:**
- Single active daemon/profile model only
- ONLINE only when `status.connected is True` and `replay_arm.profile` exact-matches
- Esc→launcher must issue zero `stop` traffic
- Quit confirm default No; `y`/`Y` only for Yes; one existing `stop` verb
- Stop failure keeps app open; never claim disconnect
- No new deps; no new daemon schema

**Accept:**
1. Unit pins: exact match; connected false / unreachable / unknown never ONLINE; status/stop never raise
2. TUI/PTY: ONLINE visible; `q` opens popup; Enter leaves daemon; `y` issues one stop; stop failure stays
3. Esc→launcher regression green (`test_play_esc_daemon_survival`)
4. Full offline suite green
5. Isolated `--run-dir` live prove optional when a daemon is available

**Proof:** focused unit + PTY + esc survival + full suite
