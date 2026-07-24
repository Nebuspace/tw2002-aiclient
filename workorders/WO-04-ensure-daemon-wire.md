# WO-04 — Ensure + daemon wire (verify)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Play entry spawns/uses the shared daemon and reaches `main_command` for a credentialed profile.

**Scope:** `tw2002_aiclient/adapters.py` (`ensure_session`, `ensure_and_sync_autopilot`, `resolve_run_dir`) · `twclient/cli.py` spawn paths

**Depends-on:** WO-03 · profile with valid `config/profiles.toml` + password in env or `config/secrets.json`

**Accept:**
- Enter play runs ensure; status becomes `ensured · Autopilot armed` or `ensured · Autopilot OFF (manual)` matching profile flag
- `run/twd.sock` exists under default `run/` (not per-profile dir unless `TW_RUN_DIR` set)
- `./tw status --json` from same seat shows `ok: true` and command prompt class after ensure
- Play screen does not hang >90s on "Ensuring session…"

**Proof (TTY + CLI):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
export TW2002_PASSWORD_<PROFILE>=...   # or secrets.json
./tw2002-aiclient
# Enter profile → wait for ready message
# second terminal:
./tw status --json | python3 -m json.tool | head -30
ls -la run/twd.sock run/twd.pid
```

Adapter tests:
```bash
.venv/bin/pytest tests/test_aiclient_adapters.py -k ensure -q
```

**Out of scope:** Autopilot tick execution · attach · cockpit viewport.

**Size:** ~30 min verify (needs live or stage server + creds).

**Canon:** `canon/architecture/session-engine.md` · `login-automaton.md`

**Status:** **Shipped** in adapters — prove on your profile tonight.
