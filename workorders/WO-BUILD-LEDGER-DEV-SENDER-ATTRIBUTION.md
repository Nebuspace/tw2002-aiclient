# WO-BUILD-LEDGER-DEV-SENDER-ATTRIBUTION

**Goal:** let Trace-Ledger attribute sacrificial `actor=dev` rows after a
send that already passed the dev-sender gate.

**Depends-on:** tip `origin/main` at `cde5914` (post #678).

**Scope:**
- `tw2002_aiclient/session/protocol.py` — `_record_ledger` uses
  `VALID_SENDERS` (includes `dev`) instead of hard `app|human`.
- `canon/doctrine/dev-drive-exception.md` — residual honesty (ledger shipped;
  CLI still open).
- `tests/test_daemon_ledger_attach.py` — pin `dev` attributed; `ai` still
  refused.
- `workorders/WO-BUILD-LEDGER-DEV-SENDER-ATTRIBUTION.md` — this file.

**Constraints:**
- Do not build `tw do --sender dev` / CLI surface here
  (`WO-BUILD-DEV-DRIVE-CLI-SURFACE`).
- Never attribute `ai`. Send-time sacrificial gate remains authoritative.

**Accept:**
- `_record_ledger(..., actor="dev")` writes a ledger row.
- `_record_ledger(..., actor="ai")` still writes nothing.
- Filter is `VALID_SENDERS`, not a duplicated pair literal.

**Proof:** pytest `tests/test_daemon_ledger_attach.py`; live-prove `n/a`
(offline attribution; no live arm).

**Refs:** queue-aiclient HIGH bank · CLAIM `2026-08-12T01:58Z`.
