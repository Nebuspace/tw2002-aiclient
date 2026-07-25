# WO-AUDIT-LOGIN-REDACTION-REHAB — Port test_login_redaction.py off twclient and un-ignore

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **STAGED** 2026-07-25 · queued behind F5-A + socket-mode + SURROGATE-ASCII Accept/Push · Max: "now-or-soon → hub picks SOON"
> Type: harden · Priority: P0 · Lens: L3 defined-but-unwired
> Refs: `tests/test_login_redaction.py` (currently `--ignore`d) · `tw2002_aiclient/session/login.py:58` · `canon/architecture/secrets-and-credentials.md`

## Goal
Port `tests/test_login_redaction.py` off `twclient` → `tw2002_aiclient`; keep sentinel + falsification teeth; un-ignore in `pytest.ini` only when green. Prove password never in: return values / `LoginError` / transcript / ledger sinks (same Accept family as module docstring `login.py:58`). Makes `login.py:58`'s written guarantee testable.

## Scope
- `tests/test_login_redaction.py` — greenfield rewrite (off `twclient`, onto `tw2002_aiclient`)
- `pytest.ini` — un-ignore when green
- No product changes; redaction sink is already `log_redacted` / `logging_util`

## Constraints
- **Dispatch order:** after F5-A + socket-mode + SURROGATE-ASCII Accept/Push (live wire/socket/--keys holes first)
- May ∥ Cursor TEST-AUDIT report triage if file-disjoint
- Sentinel + falsification teeth must be kept (not cut to trivial)
- Secrets doctrine: fixture secrets obviously-fake sentinels only

## Accept
1. `test_login_redaction.py` green + un-ignored in `pytest.ini`
2. Password never in return / `LoginError` / transcript / ledger sinks — proven with falsifying fixtures
3. Falsification teeth: a naive log-the-password implementation must fail at least one test

## Proof
Targeted + full suite; STATUS + SHA; Push waits Accept.

## Refs
Max @ 10:30 ET · hub ruling SOON · CC STAGED note @ 14:31:06Z · `login.py:58` docstring guarantee
