# WO-TEST-PROTOCOL-TRAINER-PANEL-REHAB — rehab or DELETE ignored protocol trainer panel suite

**Status:** DONE · Cursor · PR #176 · **DELETE** · awaiting hub Accept  
**Posted:** 2026-07-28T16:19Z · hub (Cursor ask · #149 AUDIT BANK-REHAB MED)

## Goal

Honest disposition for ignored `tests/test_protocol_trainer_panel.py` (twclient-era). Rehab onto in-tree protocol/trainer-panel APIs + un-ignore, **or** DELETE if archive-only and live pins supersede.

## Disposition (Cursor · evidence)

**DELETE** — not rehab.

| Evidence | Finding |
|---|---|
| Collect | `ModuleNotFoundError: twclient` (`ledger`, `skills`, `autopilot`, `MODE_AI_PILOT`, …) |
| Suite shape | Fake-daemon wire tests for `list_skills` / `play_start|stop|pause|resume` / autopilot status / intervention — **AI live-drive control panel** |
| Product | No `skills.py` / `autopilot.py`; north-star **AI never live-drives**; `test_skills.py` already DELETED (#171) |
| Live cockpit | Trainer teach/record/analyze surfaces are separate (`test_cockpit_*`); not this archive verb set |

Rehab would restore an AI-pilot protocol surface canon forbids.

## Accept

1. Evidence-based rehab+un-ignore **or** DELETE+drop `--ignore=tests/test_protocol_trainer_panel.py`. ✅ DELETE
2. No stubs. Cite live coverage if DELETE. ✅ cockpit teach/arm separate; skills gone
3. Suite green; live-prove `n/a`. Pause for LIVE-PROVE #169 if hub posts.

## Out of bounds

- CC #169 · KEEP-IGNORED haggle/crawl/trade_driver · interactive_app / spectate mega (separate)

## Refs

- `AUDIT-TEST-IGNORE-LIST-LANDMINE.md` · `canon/architecture/north-star.md`
