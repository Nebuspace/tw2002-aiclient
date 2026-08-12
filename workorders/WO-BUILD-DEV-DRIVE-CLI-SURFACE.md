# WO-BUILD-DEV-DRIVE-CLI-SURFACE

**Status:** DONE · PR #680 · tip `b64096c` — `--sender {app,dev}` on tw do/send

**Goal:** make the sacrificial `sender=dev` gate reachable from `tw do` /
`tw send` (not only REPL `Session.send`).

**Depends-on:** tip `origin/main` at `014deb4` (post #679 ledger attribution).

**Scope:**
- `tw2002_aiclient/session/protocol.py` — `_drive_sender`; do/send pass
  `sender` to `Session.send` + `_record_ledger` actor; ValueError →
  `sender_refused`.
- `tw2002_aiclient/session/cli.py` — `--sender {app,dev}` (default `app`).
- `tests/test_cli_ops_verb_b.py` — parser + dispatch pins.
- `canon/doctrine/dev-drive-exception.md` · `canon/architecture/cli-verbs.md`
- `workorders/WO-BUILD-DEV-DRIVE-CLI-SURFACE.md` — this file.

**Constraints:**
- Verb boundary allows only `app|dev` (not `human`/`ai`).
- Sacrificial refuse stays in `Session._require_dev_sender_authorized`.
- Login/ensure send paths stay `sender=app`.

**Accept:**
- `tw do … --sender dev` / `tw send … --sender dev` reach Session.send.
- Invalid sender → `invalid_sender` without sending.
- Non-sacrificial profile → `sender_refused` from Session gate.

**Proof:** pytest `tests/test_cli_ops_verb_b.py`; live-prove `n/a` unless
hub GO for sacrificial arm (offline gate proof sufficient for Accept of
this WO).

**Refs:** queue HIGH · CLAIM `2026-08-12T02:23Z`.
