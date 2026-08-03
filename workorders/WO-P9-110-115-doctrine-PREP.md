# WO-P9-110…115 — Doctrine / safety teeth · PREP

> Status: **PREP** 2026-08-03 · tip honesty · seat `impl-aiclient-cursor`  
> Phase: 9 · Type: PREP (inventory + tightened Accept/Proof) · Execute: hub HANDOFF only  
> Canon: `canon/doctrine/secrets-and-credentials.md` · `action-safety-guards.md` · `alignment-and-conduct.md` · conventions (hypothesis-tag · public-bound)  
> Refs: `ULTRACODE-WO-INVENTORY.md` Phase 9 · parent `WO-AUDIT-PHASE789-PREP.md`

**No product edited in this WO.** Live-state below is tip reality only (`aad330c`).

---

## 0. Strategic framing

- **Doctrine is teeth, not prose.** PREP marks what is enforceable in product/CI vs aspirational coach text.
- **Secrets never in logs/argv/history/repo.** Pair 110/111 with ledger work (094).
- **What already landed (tip):** credentials precedence · redaction on several paths · scattered NEVER_AUTO / Paladin / crawl guards · path-leak public-bound lint.
- **What Phase 9 still owes:** attach heuristic residual (RX transcript gate LIVE via PWO-111; live-paint residual named in doctrine). Ledger redaction LIVE via 094. Action-safety coverage map LIVE (PWO-112).
- **HOLDs:** force-push · secrets in coord · public-repo personal identifiers.

---

## 1. Tip inventory (vs canon target)

| Piece | Tip `aad330c` | Notes |
|---|---|---|
| Secrets resolve precedence | **LIVE** | `session/credentials.py` env → secrets file · credentials/redaction tests |
| Redaction on all send paths | **TX-LIVE** | `_log_tx`/`log_redacted` + LOGS + login/attach/status/ensure tests; ledger redaction LIVE via PWO-094 |
| Action-safety byte guards | **LIVE** | `action_safety.py` coverage map + unit-per-class pins; NEVER_AUTO consumer audit retained |
| Alignment no PvP aggression | **LIVE** | `alignment_gate` at `write_draft`/`promote_draft`/`bridge_to_kernel_document`; corp-toll negative control |
| Hypothesis-tag discipline CI | **LIVE** | `scripts/hypothesis_tag_ci_guard.py` in suite.yml; deliberate-fail via `--self-test-fail` |
| Public-bound lint | **LIVE** | `scripts/path-leak-scan.sh` · `scripts/githooks/pre-commit` |

---

## 2. Per-PWO Accept + Proof

### PWO-110 — Secrets resolve precedence (HARDEN) — **LIVE**
- **Depends-on:** 005
- **Accept residual:** none for PREP; Execute only on regression.
- **Proof:** `tests/test_credentials.py` · `tests/test_secrets_store_redaction.py`.
- **Hazards:** Never log resolved password.

### PWO-111 — Redaction on all send paths (HARDEN) — **TX+RX-LOG LIVE** (ledger redaction LIVE via 094)
- **Depends-on:** 020
- **Live state:** password TX routes `secret=True` → `connection._log_tx` → `TranscriptLogger.log_redacted` + `TranscriptTail.append_redacted`; RX transcript via `_log_rx` / `should_redact_rx` (password-anchor **or** post-secret window); login/attach/do--secret/status/ensure + connection RX pins green.
- **Accept residual (named, not claimed DONE):** (1) LedgerWriter redaction = **PWO-094 LIVE**; (2) live screen/`watch` paint may still show echo (doctrine residual — not the transcript log); (3) attach heuristic misses non-keyword prompts (documented residual test).
- **Proof:** `tests/test_login_redaction.py` · `test_connection.py` (RX pins) · `test_logging_util.py` · `test_attach_redaction.py` · `test_status_prompt_redaction.py` · `test_ensure_login_error_redaction.py` · `test_secrets_store_redaction.py`.
- **Hazards:** New send sites must pass `secret=`; never put passwords in `cli --keys` argv.

### PWO-112 — Action-safety byte guards (HARDEN) — **LIVE**
- **Depends-on:** 081 · 083 (satisfied)
- **Live state:** `tw2002_aiclient/action_safety.py` proven coverage map (canon ladder → source marker + proof test); `tests/test_action_safety_coverage.py`.
- **Accept residual:** none for 112 — map is the DONE claim; depth audits (e.g. NEVER_AUTO) remain referenced.
- **Proof:** `pytest tests/test_action_safety_coverage.py`.
- **Hazards:** Scattered guards alone ≠ DONE — held via map pins.

### PWO-113 — Alignment: no PvP aggression rules (HARDEN) — **LIVE**
- **Depends-on:** 070 · 081
- **Live state:** `tw2002_aiclient/alignment_gate.py` refused at writer + promote + draft bridge; `tests/test_alignment_gate.py`.
- **Accept residual:** screen-class coverage grows with classifier; fire-time remains `fighter_toll_policy`.
- **Proof:** four DoD pins (refuse write / refuse promote / refuse bridge / corp-toll allow).
- **Hazards:** Do not conflate with PWO-112 action-safety rails.

### PWO-114 — Hypothesis-tag discipline CI (HARDEN) — **LIVE**
- **Depends-on:** 100 (satisfied · tip `6824d5d`)
- **Live state:** `scripts/hypothesis_tag_ci_guard.py` runs real `assert_all_unverified_tagged` in suite.yml; `--self-test-fail` proves untagged fixture reddens.
- **Accept residual:** none for 114.
- **Proof:** `./scripts/test_hypothesis_tag_ci_guard.sh` · CI suite step.
- **Hazards:** coach_kb flags alone ≠ CI — held; guard imports real module.

### PWO-115 — Public-bound lint (HARDEN) — **LIVE**
- **Depends-on:** —
- **Accept residual:** keep hooksPath enabled per clone; Cursor fail-open + githook fail-closed dual layer.
- **Proof:** stage a leaky path → scan exit 1.
- **Hazards:** Worker host without command hooks is fail-open — githook is load-bearing.

---

## 3. Depends-on graph

```
005 ──► 110 LIVE
020 ──► 111 TX+RX-LOG LIVE (ledger redaction LIVE via 094)
081·083 ──► 112 LIVE
070·081 ──► 113 LIVE
100 ──► 114 LIVE
— ──► 115 LIVE
```

**Suggested first execute after PREP Accept:** Phase 9 TX+RX-log/ledger redaction LIVE; remaining named residual on 111 = attach heuristic (+ live-paint echo). 112–115 LIVE.

---

## 4. Hazards

1. Do not treat coach anti-PK prose as 113 DONE.
2. Path-leak LIVE ≠ secrets redaction LIVE.
3. Safety list surfaces still Max-gated for product fixes that change auth/send semantics beyond docs.

---

## 5. Execute readiness

PREP ready for hub Accept of this docs WO. Product Execute = separate HANDOFF.
