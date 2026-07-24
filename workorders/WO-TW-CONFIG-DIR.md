# WO-TW-CONFIG-DIR — Config-dir env seam for credentials

> Status: DONE (shipped `da1c875` 2026-07-24 — additive TW_CONFIG_DIR seam on credentials config paths, folded into OPEN-003-A; cross-process isolation proven; zero change to env-first password / chmod-600 / redaction.)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020 (Accept)
**Canon:** `canon/doctrine/secrets-and-credentials.md` · folds with OPEN-003 Option A (catalog-aware resolver)

**Goal:** Add an additive `TW_CONFIG_DIR` environment seam to `credentials.py` mirroring `TW_RUN_DIR` in `env.py`, so spawned-daemon / harness tests can isolate config without monkeypatching in-process paths.

**Scope (when EXECUTE):** `tw2002_aiclient/session/credentials.py` (+ thin tests) — default = current `CONFIG_DIR` when unset; zero behavior change for operators; no change to env-first password resolution, chmod-600 secrets, or redaction.

**Out of bounds until HANDOFF:** any edit to `credentials.py` (secrets-lane — hub ruled follow-on only during WO-P2-020).

**Accept (draft):** unset → same paths as today · set → profiles/secrets resolve under that dir · daemon child honors the env · scoped commit · STATUS.

**Proof (draft):** unit/harness with `TW_CONFIG_DIR` temp dir · confirm operator `config/` untouched.
