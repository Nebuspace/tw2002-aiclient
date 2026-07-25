# WO-AUDIT-HARDEN-ATTACH — Bound AttachInputConn reads

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`88004d8`** (CC · Fable 5) · docs stamp Cursor  
> Type: harden · Priority: P0 · Lens: L3 defined-but-unwired  
> Refs: `canon/findings.md` HARDEN-ATTACH-SOCKET-TIMEOUT · `session/attach_client.py`

## Tip verdict
**DONE** on origin `88004d8` — `AttachInputConn` sets `settimeout(5.0)` at connect; existing `OSError` containment covers hang→bounded return. Tripwire untouched. Proof: `tests/test_attach_client_timeouts` (+ hub re-ran tripwire green at Accept).

## Goal
Bound blocking `readline()` on `AttachInputConn` so a hung/peer-dead daemon cannot freeze the cockpit forever; contain failure to existing attach error paths.

## Scope (disjoint lanes)
- A: `tw2002_aiclient/session/attach_client.py` — timeouts on connect ack + send_key ack reads; clear `error` strings
- B: `tests/test_*attach*` — hang/timeout fixtures; prove close still releases; tripwire untouched
- C: docs — findings row → DONE or note residual when Accept’d

## Constraints
- Do **not** loosen `tests/test_spectate_no_send.py` / allowlist
- No seat-key remapping · no Human→App invent · F2/G2–G4 HOLD
- Prefer existing containment patterns (watchfeed join timeout idiom) over new deps
- One producer (CC POLISH-SAFE) — Cursor docs stamp only

## Accept
1. Connect and send_key reads cannot block unbounded (documented timeout)
2. Timeout → False/`error` set; cockpit can recover / detach without process hang
3. Tripwire green; no new send-capable shapes without adjudication
4. Suite fingerprint-bound green

## Proof
Unit/FakeDaemon timeout inject · full suite · STATUS SHA `88004d8` on origin. Push waits Accept (product already SHIPped).

## Refs
`attach_client.py` · findings HARDEN-ATTACH · hub Accept @ 05:28:02Z
