# WO-CLEANUP-PROTOCOL-DEAD-LOCAL-FINAL-CLS

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1

## Goal

`final_cls, steps = run_login(...)` in `session/protocol.py` — `final_cls` is never
read again. `steps` is returned in the success `build_response` extra.

## Fix

`_, steps = run_login(...)`.

## Accept

- [x] Unused local gone; `steps` still wired into response
- live-prove: n/a (dead-local rename; no behavior change)

## Proof

Diff review; grep confirms no remaining `final_cls` bind at that call site.
