# WO-BUILD-PLAY-TUI-DISCOVERED-ARM-HARNESS — BANKED

**Status:** BANKED (hub park 2026-08-09 · WO-AI-TRANCHE-9 close-out) — not in active build queue.

**Goal:** Dedicated harness (or operator-attended script) that drives Play chrome
`L` → select discovered chain → confirm → `T` against a live sacrificial session,
proving the TUI path (not only `tw chain start`).

**Why banked:** CLI discovered-chain full cycle already live-proven
(`outcome=completed`). Headless PTY Play drive failed to leave profile-select
reliably; re-attempts are out of tranche scope until this harness exists or an
operator attends Play once.

**Depends-on:** none for design; live prove needs `crawl_sacrificial` profile.
**Refs:** queue `WO-BUILD-PLAY-CHAINS-DISCOVERED-ARM-LIVE-PROOF` · tranche-9 STATUS.
