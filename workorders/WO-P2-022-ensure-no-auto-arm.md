# WO-P2-022 — Ensure `--no-auto-arm`

> Status: DONE — shipped (awaiting hub Accept; tip commit this STATUS)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020
**Canon:** `canon/architecture/app-autopilot-model.md`, `canon/architecture/north-star.md` (The Win
Condition — the human is never sidelined by a rising automation number)

**Goal:** Guarantee `ensure` never surprise-arms the App autopilot as a side effect of reaching
`main_command` — arming is always a separate, explicit, confirm-gated act.

**Scope:** `tw2002_aiclient/session/cli.py` (`ensure` verb's `--no-auto-arm` flag, default behavior),
`tw2002_aiclient/adapters.py` (`ensure_session` call site).

**Shipped (verify-first):** ensure never arms by construction (`autopilot.py` not ported); help text
updated so `--no-auto-arm` is an explicit no-op-confirm; `status --json` stub
`autopilot: {running: false}`; proving tests in `tests/test_ensure_no_auto_arm.py`.

**Accept:**
- After a bare `ensure` (no flags) against a profile whose stored `autopilot` flag is `true`, `tw
  status --json` shows the App is **not** actively driving — reaching `main_command` alone never
  starts autopilot playback.
- `ensure --no-auto-arm` is accepted as an explicit no-op-confirming flag (present for symmetry with
  any future default-arm proposal) and produces identical non-arming behavior to the bare call.
- Arming the App still requires the separate, confirm-gated cockpit action (out of scope here —
  this WO only proves ensure itself never arms).

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
# profile with autopilot=true in config/profiles.toml
.venv/bin/python -m tw2002_aiclient.session.cli ensure --profile <profile>
.venv/bin/python -m tw2002_aiclient.session.cli status --json | python3 -m json.tool   # autopilot not actively driving
.venv/bin/python -m tw2002_aiclient.session.cli ensure --profile <profile> --no-auto-arm
.venv/bin/python -m tw2002_aiclient.session.cli status --json | python3 -m json.tool   # same result
```
