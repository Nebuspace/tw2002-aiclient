# WO-TEST-HUD-SEED-REHAB — rehab or DELETE ignored HUD seed suite

**Status:** DONE · Cursor · PR #174 · **DELETE** · awaiting hub Accept  
**Posted:** 2026-07-28T16:07Z · hub (Cursor ask · #149 AUDIT BANK-REHAB)

## Goal

Honest disposition for ignored `tests/test_hud_seed.py` (twclient-era). Partial live cockpit HUD coverage exists — rehab onto in-tree HUD/seed APIs + un-ignore, **or** DELETE if archive-only and live pins supersede.

## Disposition (Cursor · evidence)

**DELETE** — not rehab.

| Evidence | Finding |
|---|---|
| Collect | `ModuleNotFoundError: twclient` (`from twclient.hud_seed import seed_hud_after_join`) |
| Product | No `hud_seed` module in tree; `cockpit/hud.py` is a **pure per-tick renderer** and explicitly defers cold-join ``I``-probe seed as a **sibling WO / fold-in, not built here** (module docstring Scope boundary) |
| Live pins that supersede (composer) | `tests/test_cockpit_hud.py` · `tests/test_cockpit_hud_pty.py` |

Rehab would invent the missing product surface. Porting `seed_hud_after_join` is a product WO, not a test-only lift.

## Accept

1. Evidence-based rehab+un-ignore **or** DELETE+drop `--ignore=tests/test_hud_seed.py`. ✅ DELETE
2. No stubs. Leave import-hygiene vacuity untouched. ✅
3. Suite green; live-prove `n/a`. Pause for LIVE-PROVE #169 if hub posts.

## Out of bounds

- CC #169 · KEEP-IGNORED haggle/crawl/trade_driver · spectate mega-suite (separate WO)

## Refs

- `AUDIT-TEST-IGNORE-LIST-LANDMINE.md` · `tw2002_aiclient/cockpit/hud.py`
