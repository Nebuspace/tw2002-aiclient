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
- Tip `trade_driver.py` still documents **Auto-haggle OFF** (accept-default
  only). This WO lands the tip-owned resolver + tests; enabling counters on
  the trade path / rule-fire arming is a follow-on (explicit claim).

Proof:

```sh
.venv/bin/python -m pytest tests/test_haggle.py -n0
```
