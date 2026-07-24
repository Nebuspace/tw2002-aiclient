# WO-P2-028 — Idle-keepalive OFF on unsafe screens

> Status: PLANNED (greenfield · **PREP DONE** 2026-07-24 · product execute blocked until a lifting HANDOFF)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-027
**Canon:** `canon/architecture/resilience-and-reconnect.md` (Conservative Idle-Keepalive)

**Goal:** Build the `SessionGuardian`'s idle-keepalive nudge with its hard safety invariant intact —
it fires only when the current screen classifies as `main_command`, and stays silent on every other
screen, so a blank Enter never commits a purchase or confirms a destructive action.

**Scope:** `tw2002_aiclient/session/guardian.py` (idle-keepalive facet, sharing the poll thread with WO-P2-027's
reconnect logic).

**Out of bounds (prep + until execute HANDOFF):** `credentials.py` · resolver · `env.py`/`cli.py`/`protocol.py`
edits while OPEN-003-A in flight · reconnect/login-replay product (WO-P2-027) · ledger module if still
unported (Accept may prove `sender=app` via send kwargs / fake ledger until P2-025 execute lands).

---

## PREP inventory (2026-07-24 — WO-P2-028-PREP · parallel fan-out)

### Verify-first verdict

**Zero live D10 supervisor.** No `guardian.py` (same gap as 027). Archive
`twclient/guardian.py` `_maybe_keepalive` (~45s threshold, `main_command`-only blank Enter) matches
mechanical canon; live only has RX `last_rx` / `idle_ms` status reporting. Execute = port keepalive
facet onto SessionGuardian (depends on 027 poll thread) + rewrite ignored `-k keepalive` tests;
close archive actor-tag gap (`sender=app`).

### Live / archive surface (file:line)

| Canon behavior | Where | vs canon |
|----------------|-------|----------|
| Guardian owns keepalive on shared poll | Live absent (`daemon.py:12–14`); archive `guardian.py:37–46`, `_tick` `88–103` | **GAP live** |
| Idle threshold under first inactivity warning | Archive `_IDLE_KEEPALIVE_MS=45_000` · gate `141–145` | **GAP live** |
| Idle clock | Live `last_rx` only (`connection.py:25,56`; `session.py:221–222`) | **partial** (RX-only) |
| Blank Enter nudge | Archive `session.send("", enter=True, secret=False)` ~155 | **GAP live** |
| Fire **only** on `main_command` | Archive `151–153`; classifier live `classify.py:496` | **GAP live** (classifier OK) |
| OFF on password/trade/confirm/combat/unknown | Archive refuse non-`main_command` | **GAP live** |
| App-class actor tag | Archive send untagged (canon notes divergence) | **GAP** both — execute must tag `app` |
| `idle_ms` status reporting | Live `protocol.py:88–89` | status-only, not keepalive |

### Accept (tightened draft for execute)

1. Keepalive may send **iff** `classify_screen(...) == "main_command"`; any other class → **zero** sends even when idle ≥ threshold.
2. When it fires: exactly one blank Enter (`""` + enter); not a typed command; not `secret=True`.
3. Send is actor-tagged **`app`** (never AI; no operator-intent).
4. Idle past configurable `idle_keepalive_ms` (default under first inactivity warning; archive **45s**); no send below threshold.
5. ≤ one keepalive per idle window (send resets / suppresses until idle again).
6. While disconnected / reconnect+replay in flight → **no** keepalive (drop path owns the poll).

### Proof (tightened draft)

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/pytest tests/test_guardian.py -k keepalive -q
# assert: main_command idle → one blank + actor=app
# assert: password | port_trade | confirm | combat | unknown → sent == []
# assert: below threshold → []; second tick same window → still ≤1
# assert: connected=False → keepalive not invoked
# live (optional): idle main_command → one blank in ledger; idle port_trade → zero
```

### Tests touch list

| File / slice | Role under 028 |
|--------------|----------------|
| `tests/test_guardian.py` `-k keepalive` (5) | **Primary** — ignored DEFER; rewrite/un-ignore on execute |
| same file `-k reconnect` | **WO-P2-027** — leave alone |
| Other `tests/` keepalive hits | **none** |

### Edge cases (pin in tests)

| Case | Expect |
|------|--------|
| Idle `main_command` ≥ threshold | 1 blank, `app` |
| Idle < threshold on `main_command` | 0 |
| Idle password / port_trade / confirm / combat / unknown | 0 |
| Mid-reconnect / disconnected tick | 0 keepalive |
| Two ticks without idle reset after fire | still ≤1 |

---

## Original Accept / Proof (pre-prep)

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
