# WO-BUILD-SESSION-END-AUTO-REPORT

**Goal:** unprompted post-session action report print at session exit.

**Depends-on:** tip `origin/main` at `73eb471` (post #677).

**Scope:**
- `tw2002_aiclient/session/cli.py` — `cmd_stop` prints `format_session_report`
  after successful stop (non-`--json`); best-effort, never fails stop.
- `tw2002_aiclient/session_report.py` — delivery docstring tip-true.
- `canon/engine/post-session-action-report.md` — flip "not yet" honesty.
- `tests/test_session_report.py` — stop auto-print + json skip pins.
- `workorders/WO-BUILD-SESSION-END-AUTO-REPORT.md` — this file.

**Constraints:**
- Offline. Do not change `--json` stop to multi-document stdout.
- Do not invent daemon-process stdout hooks; CLI stop is the operator-visible
  session-exit path.

**Accept:**
- Successful `tw stop` (human mode) prints the same digest shape as `tw report`.
- `--json` stop does not append the text digest.
- Canon no longer claims the auto-print is unbuilt.

**Proof:** pytest `tests/test_session_report.py`; live-prove `n/a`.

**Refs:** queue cycle-52 · IDLE-KICK claim `2026-08-12T01:33Z`.
