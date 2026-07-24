# WO-OPEN-003 — Host/port resolver consolidation (catalog-aware)

> Status: DONE (code shipped `da1c875` 2026-07-24 — one catalog-aware resolver + typed subtypes; Cipher CLEAN + Mack HIGH/LOW fixed. DECISIONS OPEN-003 stays OPEN/Pending until the human formally marks it RESOLVED/CLOSED.)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020 (Accept) · OPEN-003 Option A Max GO
**Canon:** `canon/DECISIONS.md` OPEN-003 · `canon/architecture/session-engine.md` (Config Bootstrap) ·
`canon/surfaces/entry-and-profile-selection.md` · `canon/doctrine/secrets-and-credentials.md`

**Goal:** Replace divergent host/port resolvers with **one catalog-aware resolver** so daemon
bootstrap, CLI ensure, protocol profile load, and credentials profile summaries agree: preferred
path is `profile.server` → `config/servers.toml`; explicit `host`/`port` remain overrides.

**Scope (when EXECUTE):** thin shared helper (likely under `session/credentials.py` or a tiny
`session/resolve.py`) · wire `env.resolve_host_port` / `cli._resolve_profile_connection` /
`protocol._load_profile` onto it · proving tests · canon Config Bootstrap prose update (docs win
after Max GO). Optional fold with `WO-TW-CONFIG-DIR` if Max wants one secrets-lane pass.

**Out of bounds until HANDOFF + Max GO:** any product edit · `credentials.py` password paths ·
`session/login.py`.

**Accept (draft):**
- Catalog-only profile (`server=…`, no host/port) resolves for daemon + CLI the same as summaries.
- Explicit host/port on the profile override the catalog.
- Env / CLI / dotenv precedence tiers above profiles.toml still win (unchanged).
- One importable resolver; duplicate catalog walks gone or thin wrappers.
- Scoped commit · STATUS.

**Proof (draft):**
```bash
.venv/bin/python -m pytest tests/test_env.py tests/test_cli_run_dir.py -q
# + new thin tests for server= catalog resolution / override / unknown key
```

**Refs:** OPEN-003 staging block in `canon/DECISIONS.md` · hub lean Option A (2026-07-24).
