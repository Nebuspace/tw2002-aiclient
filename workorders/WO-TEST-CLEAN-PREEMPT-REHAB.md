# WO-TEST-CLEAN-PREEMPT-REHAB — rehab or DELETE ignored clean_preempt suite

**Status:** DONE · Cursor · PR #175 · **DELETE** · awaiting hub Accept  
**Posted:** 2026-07-28T16:12Z · hub (Cursor ask · #149 AUDIT BANK-REHAB · control fence)

## Goal

Honest disposition for ignored `tests/test_clean_preempt.py` (twclient-era). Control preempt / fence may still be product-critical — rehab onto in-tree APIs + un-ignore, **or** DELETE if archive-only and live control-lock / preempt pins supersede.

## Disposition (Cursor · evidence)

**DELETE** — not rehab. The **fence itself** is product-critical and already pinned; this file's unique load was archive protocol/ledger plumbing that is gone.

| Evidence | Finding |
|---|---|
| Collect | `ModuleNotFoundError: twclient` (`protocol`, `ControlLock`, `LedgerWriter`) |
| Archive shape | `protocol.dispatch` do/send/haggle → Trace-Ledger `interrupted_by_human`; `record_attach_keystroke` actor/secret; wiring `is_driver_fenced` into skills/crawl |
| Reborn gaps for those proofs *(at DELETE time)* | attach Trace-Ledger was deferred then; **LIVE now** (#353/#355). `tests/test_skills.py` already DELETED (#171). DELETE disposition unchanged — fence covered by live control-lock pins. |
| Live superseding fence pins | `tests/test_control_lock.py` (WO-CLEANPREEMPT fence courtesy + autoloop fence blocks) · `tests/test_wedged_send_fence.py` · session `is_driver_fenced` / `take_human` |

Rehab would invent ledger + archive `do`/`send` interrupt flagging, not lift a still-live contract.

## Accept

1. Evidence-based rehab+un-ignore **or** DELETE+drop `--ignore=tests/test_clean_preempt.py`. ✅ DELETE
2. No stubs. Cite which live tests cover the fence if DELETE. ✅ above
3. Suite green; live-prove `n/a`. Pause for LIVE-PROVE #169 if hub posts.

## Out of bounds

- CC #169 · KEEP-IGNORED haggle/crawl/trade_driver

## Refs

- `AUDIT-TEST-IGNORE-LIST-LANDMINE.md` · `session/control_lock.py` · `session/daemon.py`
