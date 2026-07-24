# WO-P0-005 — Config and secrets layout

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 0 · **Type:** bootstrap · **Depends:** WO-P0-003
**Canon:** `canon/doctrine/secrets-and-credentials.md`

**Goal:** Lay down the two on-disk config homes the doctrine requires — the tracked non-secret
profile-shape template and server catalog, and the gitignored local real files — with
environment-first password resolution wired before any login code exists.

**Scope:** `config/profiles.toml.example` (tracked), `config/servers.toml` (tracked, public catalog),
`.gitignore` entries for `config/profiles.toml` and `config/secrets.json`, a minimal
`tw2002_aiclient/session/credentials.py` stub exposing `get_password(profile)` with the env-first →
chmod-600-secrets-file precedence (secrets file itself may be empty/absent at this stage).

**Accept:**
- `config/profiles.toml.example` and `config/servers.toml` exist, are tracked, and contain no
  password field of any kind.
- `config/profiles.toml` and `config/secrets.json` are listed in `.gitignore` and, if created during
  proof, are **not** shown by `git status --porcelain`.
- `get_password("scratch")` with `TW2002_PASSWORD_SCRATCH` set in the environment returns that value
  without touching `config/secrets.json`.
- `get_password("scratch")` with no env var and no secrets-file entry returns `None` (absence, not an
  exception) — matches the doctrine's "absent is legitimate" contract.
- Any real `config/secrets.json` created by the resolver is written mode `0600`.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
git status --porcelain config/                                 # profiles.toml/secrets.json absent or untracked+ignored
export TW2002_PASSWORD_SCRATCH=throwaway
.venv/bin/python -c "from tw2002_aiclient.session.credentials import get_password; print(get_password('scratch'))"
unset TW2002_PASSWORD_SCRATCH
.venv/bin/python -c "from tw2002_aiclient.session.credentials import get_password; print(get_password('scratch'))"  # None
```
