# WO-PLAY-CONN-TOGGLE

**Status:** **HOLD** · Max pace-down (local app restart) · do **not** dispatch until hub lifts HOLD  
**Posted:** 2026-07-26 · Max live report (timed-out game board; no obvious reconnect; Connected not actionable)  
**Seat (when lifted):** Cursor preferred (play chrome / `screens.py` / control_seat) · CC if daemon reconnect verbs needed  
**Related:** `WO-PLAY-GAME-LETTER-AUTOSELECT` (sibling — auto letter) · `WO-P2-027` reconnect/login-replay · `WO-P3-030` play chrome · guardian reconnect

## Goal

In the play / cockpit chrome, the connection state (**Connected** / **Disconnected**) must be an **arrow-key-accessible, activatable control**:

| Showing | Activate (Enter / click-equivalent) | Result |
|---|---|---|
| **Connected** | toggle | disconnect cleanly → UI shows **Disconnected** (daemon/session policy per canon — do not strand a silent half-dead telnet) |
| **Disconnected** (incl. after host game-select **timed out** / drop) | toggle | trigger reconnect (ensure/login-replay or documented reconnect verb) → UI shows reconnecting then **Connected**, or an honest failure |

Today Max can see Manual control + a timed-out ANSI board and has **no obvious in-aiclient way to reconnect**; it also does **not** appear to reconnect on its own.

## Constraints

- Arrow-key reachable (keyboard-first cockpit) — not mouse-only.
- Must not look like a decorative status chip that cannot take focus.
- Reconnect must use existing ensure/guardian/reconnect paths where possible (`WO-P2-027` / status truth) — do not invent a second silent reconnect loop.
- While Max HOLD is active: **no** live `./tw ensure|status|stop` against shared runtime; design + unit/pty pins only until HOLD lifts.
- Esc / daemon-survival (ADR-001) stays: chrome disconnect must not accidentally kill the wrong process; reconnect must not steal another profile's default daemon (`--run-dir` / footgun discipline).
- Pixel pass on labels/focus/a11y structure when UI lands.

## Accept

1. From play shell with focusable Connected control: activate → Disconnected (status + border tone honesty).
2. From Disconnected: activate → reconnect attempt visible (reconnecting affordance or status text) → Connected on success, or honest error on failure.
3. After a host-side game-select timeout / drop (simulated in test ok): Disconnected path still offers reconnect — operator is not stuck with only Manual + dead board.
4. Pins cover focus order (arrow keys reach the control) + activate behavior; no regression on Manual / App / Spectate seat labels.

## Proof

```text
# after HOLD lift
pytest tests/test_play_chrome_nav.py tests/test_cockpit_tones.py -q -n0
# + new pins for conn toggle focus + activate + reconnect affordance
# live (isolated run-dir): Connected→Disconnected→reconnect→Connected
```

## Refs

- `tw2002_aiclient/screens.py` (`PlayShellScreen`, connected snapshot)
- `tw2002_aiclient/cockpit/control_seat.py` (`MANUAL_LABEL` / seat chrome)
- `tw2002_aiclient/session/protocol.py` (`connected` on status)
- `canon/surfaces/trainer-cockpit.md` (reconnect_exhausted)
- Sibling: `WO-PLAY-GAME-LETTER-AUTOSELECT.md`
