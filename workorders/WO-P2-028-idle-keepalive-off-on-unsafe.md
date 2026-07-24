# WO-P2-028 — Idle-keepalive OFF on unsafe screens

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-027
**Canon:** `canon/architecture/resilience-and-reconnect.md` (Conservative Idle-Keepalive)

**Goal:** Build the `SessionGuardian`'s idle-keepalive nudge with its hard safety invariant intact —
it fires only when the current screen classifies as `main_command`, and stays silent on every other
screen, so a blank Enter never commits a purchase or confirms a destructive action.

**Scope:** `tw2002_aiclient/session/guardian.py` (idle-keepalive facet, sharing the poll thread with WO-P2-027's
reconnect logic).

**Accept:**
- Idling on the main command prompt past the configured threshold produces exactly one blank
  keystroke send, actor-tagged `app`, and no more than one per idle window.
- Idling on a port/trade screen ("How many holds… [N]?") past the same threshold produces **zero**
  keystrokes — the keepalive classifies the screen and stays its hand.
- Idling on a password/credential prompt or a confirm/yes-no screen likewise produces zero
  keystrokes.
- The keepalive send (when it does fire) is visible in the trace ledger as an `app`-actor row with
  no `intent` implying it was operator-initiated.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/pytest tests/test_guardian.py -k keepalive -q
# live: sit idle on main_command past the threshold, confirm exactly one blank send in the ledger
# live: sit idle on a port_trade screen past the threshold, confirm zero sends
tail -5 state/ledger.jsonl
```
