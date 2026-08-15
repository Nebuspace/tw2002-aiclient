# WO-AICLIENT-WIRE-PANIC-ALSO-STOPS-EXPLORE

**Goal:** Canon's panic / all-automation halt must stop explore (and every
other play-surface runner), not autoloop alone. Tip-honest docs + structural
pin.

**Tip note (verify-first):** `app.py`'s `action == "panic"` block already
called `explore_stop` (+ `trade_chain_stop`) since #267. The queue premise
was tip-stale relative to **docs** (`panic.py` / `adapters.autoloop_stop`
still claimed explore was excluded). Calm-path `P` remains Port Trade;
Mode-leave already used `_stop_live_runners`.

**Scope:**
- Route panic action through `_stop_live_runners` (adds `stardock_hold_stop`
  + clears `hold_poll_active`)
- Tip-honest `cockpit/panic.py` + `adapters.autoloop_stop` docs
- Pins in `tests/test_cockpit_panic.py`

**Accept:**
- Panic halt path includes `explore_stop` (via `_stop_live_runners`)
- Docs no longer claim explore is excluded
- Partial failures still reported honestly

**Proof:**
- `.venv/bin/python -m pytest tests/test_cockpit_panic.py tests/test_play_strip_policy_auto.py -q -k 'stop_live or panic_docs or panic_action or stop_live_runners'`
- `live-prove: n/a` — offline halt-wire / docstring honesty; no live-drive
