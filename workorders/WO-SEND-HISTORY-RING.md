# WO-SEND-HISTORY-RING

## Goal

Make the raw protocol `send` verb record into the session history ring, so
`tw history` / the history API shows operator-driven raw sends the same way
`do` and armed-run sends already do.

## Scope

- `tw2002_aiclient/session/protocol.py` (`verb == "send"` path)
- focused tests under `tests/` (extend existing history / protocol pins or add
  a small dedicated file)

## Constraints

- Smallest change: after a successful raw send, call the existing
  `session.record_history(...)` with verb `"send"` (or the house constant if
  one already exists for this surface). Do not invent a second ledger.
- Keep `send` raw: no settle wait, no classification invent, no attach behavior
  change.
- Secret redaction must match `do`: if `secret=True`, history args redact
  `input` rather than storing the secret.
- Do not change armed-run history (`autoloop` / `HISTORY_VERB_AUTOLOOP`),
  attach history, or `do`/`read` behavior beyond shared helper reuse if
  genuinely smaller.
- No UI/canon/deps/`app.py` (#218 frozen) / live runtime changes.

## Accept

1. Dispatching protocol `send` with a known input appends a history row whose
   verb identifies the raw send and whose args carry that input (or the
   redacted marker when secret).
2. Secret sends never place the secret plaintext in the history ring.
3. Existing `do` / armed-run / attach history pins remain green.
4. Focused tests + full offline suite pass.
5. Live prove is `n/a` (observability of an existing offline-dispatchable
   path; no new TWGS action required).

## Proof

```bash
pytest -q tests/test_arm_history_ring.py tests/test_*history* tests/test_*protocol*  # as applicable
pytest -q tests
```

STATUS must name the exact history verb/field used and show a before/after or
assert that `send` now appears in `session.history` / history response.

## Refs

- Sibling banked from #225 `WO-ARM-HISTORY-RING` (CC: `send` at protocol.py
  records nothing)
- `tw2002_aiclient/session/protocol.py` `verb == "send"` (~1035+)
- `Session.record_history` · `do` path redaction pattern
- Depends on `main` @ `268df74`
