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
- **What Phase 9 still owes:** full send-path redaction audit · unified action-safety module (or proven coverage map) · teacher PvP rejection gate · hypothesis-tag CI script.
- **HOLDs:** force-push · secrets in coord · public-repo personal identifiers.

---

## 1. Tip inventory (vs canon target)

| Piece | Tip `aad330c` | Notes |
|---|---|---|
| Secrets resolve precedence | **LIVE** | `session/credentials.py` env → secrets file · credentials/redaction tests |
| Redaction on all send paths | **TX-LIVE** | `_log_tx`/`log_redacted` + LOGS + login/attach/status/ensure tests; ledger = PWO-094 MISSING |
| Action-safety byte guards | **PARTIAL** | NEVER_AUTO · classify · crawler · trade_driver Paladin · sector_explore — scattered, no unified module |
| Alignment no PvP aggression | **LIVE** | `alignment_gate` at `write_draft`/`promote_draft`/`bridge_to_kernel_document`; corp-toll negative control |
| Hypothesis-tag discipline CI | **MISSING** | `coach_kb` flags / params exist; no CI script failing untagged numbers |
| Public-bound lint | **LIVE** | `scripts/path-leak-scan.sh` · `scripts/githooks/pre-commit` |

---

## 2. Per-PWO Accept + Proof

### PWO-110 — Secrets resolve precedence (HARDEN) — **LIVE**
- **Depends-on:** 005
- **Accept residual:** none for PREP; Execute only on regression.
- **Proof:** `tests/test_credentials.py` · `tests/test_secrets_store_redaction.py`.
- **Hazards:** Never log resolved password.

### PWO-111 — Redaction on all send paths (HARDEN) — **TX-LIVE** (ledger deferred)
- **Depends-on:** 020
- **Live state:** password TX routes `secret=True` → `connection._log_tx` → `TranscriptLogger.log_redacted` + `TranscriptTail.append_redacted`; login/attach/do--secret/status/ensure suites green.
- **Accept residual (named, not claimed DONE):** (1) LedgerWriter redaction = **PWO-094**; (2) RX screen/prompt verbatim by canon; (3) attach heuristic misses non-keyword prompts (documented residual test).
- **Proof:** `tests/test_login_redaction.py` · `test_attach_redaction.py` · `test_status_prompt_redaction.py` · `test_ensure_login_error_redaction.py` · `test_secrets_store_redaction.py`.
- **Hazards:** New send sites must pass `secret=`; never put passwords in `cli --keys` argv.

### PWO-112 — Action-safety byte guards (HARDEN) — **PARTIAL**
- **Depends-on:** 081 · 083
- **Accept residual:** destructive macros blocked with one proven coverage map (module or documented inventory + tests).
- **Proof:** unit per guard class.
- **Hazards:** Scattered guards ≠ complete coverage — do not claim DONE without map.

### PWO-113 — Alignment: no PvP aggression rules (HARDEN) — **LIVE**
- **Depends-on:** 070 · 081
- **Live state:** `tw2002_aiclient/alignment_gate.py` refused at writer + promote + draft bridge; `tests/test_alignment_gate.py`.
- **Accept residual:** screen-class coverage grows with classifier; fire-time remains `fighter_toll_policy`.
- **Proof:** four DoD pins (refuse write / refuse promote / refuse bridge / corp-toll allow).
- **Hazards:** Do not conflate with PWO-112 action-safety rails.

### PWO-114 — Hypothesis-tag discipline CI (HARDEN) — **MISSING**
- **Depends-on:** 100
- **Accept:** untagged numbers fail check in CI.
- **Proof:** script + fixture fail case.
- **Hazards:** Depends on 100 param surface; coach_kb flags alone ≠ CI.

### PWO-115 — Public-bound lint (HARDEN) — **LIVE**
- **Depends-on:** —
- **Accept residual:** keep hooksPath enabled per clone; Cursor fail-open + githook fail-closed dual layer.
- **Proof:** stage a leaky path → scan exit 1.
- **Hazards:** Worker host without command hooks is fail-open — githook is load-bearing.

---

## 3. Depends-on graph

```
005 ──► 110 LIVE
020 ──► 111 TX-LIVE (ledger pairs with 094)
081·083 ──► 112 PARTIAL
070·081 ──► 113 LIVE
100 ──► 114 MISSING
— ──► 115 LIVE
```

**Suggested first execute after PREP Accept:** **PWO-112 coverage map** or **PWO-114** (after 100/092). 113 LIVE.

---

## 4. Hazards

1. Do not treat coach anti-PK prose as 113 DONE.
2. Path-leak LIVE ≠ secrets redaction LIVE.
3. Safety list surfaces still Max-gated for product fixes that change auth/send semantics beyond docs.

---

## 5. Execute readiness

PREP ready for hub Accept of this docs WO. Product Execute = separate HANDOFF.
