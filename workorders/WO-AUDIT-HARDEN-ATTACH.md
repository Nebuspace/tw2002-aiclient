# WO-AUDIT-HARDEN-ATTACH — Bound AttachInputConn reads

> Status: **DRAFT** 2026-07-25 · AUDIT-OKF-6LENS · tip `d4a8829`  
> Type: harden · Priority: P0 · Lens: L3 defined-but-unwired  
> Refs: `canon/findings.md` HARDEN-ATTACH-SOCKET-TIMEOUT · `session/attach_client.py`

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
- CC POLISH-SAFE may already own this overnight — coordinate; one producer

## Accept
1. Connect and send_key reads cannot block unbounded (documented timeout)
2. Timeout → False/`error` set; cockpit can recover / detach without process hang
3. Tripwire green; no new send-capable shapes without adjudication
4. Suite fingerprint-bound green

## Proof
Unit/FakeDaemon timeout inject · full suite · STATUS SHA. Push waits Accept.

## Refs
`attach_client.py:37,60` · findings HARDEN-ATTACH · hub POLISH-SAFE ACK
