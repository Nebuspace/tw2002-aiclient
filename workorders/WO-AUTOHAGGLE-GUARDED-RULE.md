# WO-AUTOHAGGLE-GUARDED-RULE

Goal: Port the deterministic, guarded OFFER resolver as a tip-owned session
rule without enabling automatic trade-path firing.

Scope:
- `tw2002_aiclient/session/haggle.py`
- `tests/test_haggle.py`

Accept:
- The resolver uses the tip settle layer and strict credit reader.
- It sends only after a fresh live OFFER proof and confirms every send.
- It reports a resolved deal only with a consistent credit delta or a
  current-line resolution shape with acceptance context.
- A stale or bare command prompt is `desync_fallback`.
- The haggle tests import the tip module, never `twclient`.
- This worktree's tip has no `trade_driver.py`; no trade-chain integration
  or automatic arming is included until a later rule-arming work order.

Proof:

```sh
.venv/bin/python -m pytest tests/test_haggle.py -n0
```
