# WO-ENSURE-PROFILE-IDENTITY-VERIFY — ensure must refuse wrong-profile session reuse

**Status:** OPEN EXECUTE · HIGH · money-path adjacent · Claude Code preferred  
**Posted:** 2026-07-28T02:52Z · hub bank from #128 live-prove (CC)  
**Refs:** CC DECISION-NEEDED 2026-07-28T02:51:51Z · ensure ok:True on wrong profile while stop in flight

## Goal
`ensure --profile X` must guarantee the live session belongs to profile X (host/identity), not merely that *some* session is at a desired screen class.

## Observed defect
`ensure --profile scout_academy` returned `ok: True · classification: main_command · steps: 0` while the screen was sector 8559 on **gone_rogue** (wrong profile/server). Stop was in flight; ensure treated a matching classification as success.

## Accept
1. On mismatch of session profile/host vs requested profile → **refuse** (not silent reuse); named error.
2. Pin: stop-in-flight / concurrent session race cannot yield ok:True for the wrong profile.
3. Suite + STATUS; live-prove preferred (safe half OK if race hard to force offline).

## Constraints
Public-repo safe. Do not widen #128. Money-path adjacent — Cipher glance on Accept.
