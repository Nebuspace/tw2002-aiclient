# WO-TRADE-AUTOFIRE-ANCHOR

**Goal:** App-armed Port Trade auto-fire must only start a chain whose **start sector == current ship sector** (prefer-current), and must **backoff** on `start_anchor_mismatch` / `start_anchor_unknown` instead of re-firing the global best every idle tick.

**Context (hub live prove 2026-08-01, Cartogra @ 3rdage):**
- Ship at 3886 / 2260 while FOCUS bubble / auto-fire repeatedly started the longest cycle anchored at **sector 8**.
- Runner halted `start_anchor_mismatch:<here>:8` or `start_anchor_unknown` (mid-`port_trade` / dirty prompt).
- Auto-fire is **not** in `_TRADE_AUTO_FIRE_BACKOFF_REASONS` for those outcomes → spam + race against explore gather / CLI prove.
- `bubble_subject(current_sector=…)` already exists (WO-CHAIN-BUBBLE-PREFER-CURRENT); auto-fire / plan path must actually use it and refuse non-matching fingerprints.

**Scope (owned paths):**
- `tw2002_aiclient/app.py` — `_autonomy_auto_fire` / trade cooldown reasons
- `tw2002_aiclient/focus_status.py` / `chain_status.py` — only if needed so FOCUS ungated `run_chain` is prefer-current
- `tw2002_aiclient/trade_chain_plan.py` — only if plan fingerprint selection needs the same gate
- pins under `tests/` for: auto-fire skips wrong-anchor chain; backoff on `start_anchor_*`; prefer-current still starts when ship is on anchor

**Constraints:**
- Do not invent navigate-to-anchor in this WO (bank separately if wanted).
- Do not change explore gather `P T 0` semantics.
- No self-merge. Live: prefer offline pins; live diversity stays #283.

**Accept:**
1. With Port Trade ·ON + APP-ARMED, if best global chain starts at sector A and ship is at B≠A → **do not** call `trade_chain_start` for that fingerprint (status may say why once).
2. If a chain **does** start at current sector → auto-fire may start it (existing cash/turn gates unchanged).
3. After a trade run ends with reason prefix `start_anchor_mismatch` or `start_anchor_unknown`, auto-fire applies the same 45s (or existing) cooldown quieting as partial-discovery backoff until marker moves.
4. Pins cover (1)–(3); full suite green.

**Proof:** suite + focused pins. Live NOT-ATTEMPTED OK if offline Accept met (hub already live-repro'd).
