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
| Redaction on all send paths | **PARTIAL** | logging_util · transcript_tail · login/attach/macro tests; ledger path incomplete |
| Action-safety byte guards | **PARTIAL** | NEVER_AUTO · classify · crawler · trade_driver Paladin · sector_explore — scattered, no unified module |
| Alignment no PvP aggression | **MISSING** | coach prose only (`toll_math` anti-PK); no teacher/rule rejection gate |
| Hypothesis-tag discipline CI | **MISSING** | `coach_kb` flags / params exist; no CI script failing untagged numbers |
| Public-bound lint | **LIVE** | `scripts/path-leak-scan.sh` · `scripts/githooks/pre-commit` |

---

## 2. Per-PWO Accept + Proof

### PWO-110 — Secrets resolve precedence (HARDEN) — **LIVE**
- **Depends-on:** 005
- **Accept residual:** none for PREP; Execute only on regression.
- **Proof:** `tests/test_credentials.py` · `tests/test_secrets_store_redaction.py`.
- **Hazards:** Never log resolved password.

### PWO-111 — Redaction on all send paths (HARDEN) — **PARTIAL**
- **Depends-on:** 020
- **Accept residual:** every send/log/ledger path redacts; scan clean.
- **Proof:** redaction tests + `rg` of send sites + ledger sample when 094 lands.
- **Hazards:** New send sites must route through the sink.

### PWO-112 — Action-safety byte guards (HARDEN) — **PARTIAL**
- **Depends-on:** 081 · 083
- **Accept residual:** destructive macros blocked with one proven coverage map (module or documented inventory + tests).
- **Proof:** unit per guard class.
- **Hazards:** Scattered guards ≠ complete coverage — do not claim DONE without map.

### PWO-113 — Alignment: no PvP aggression rules (HARDEN) — **MISSING**
- **Depends-on:** 070 · 081
- **Accept:** teacher/rule pipeline rejects PvP-harm proposals.
- **Proof:** unit reject fixtures.
- **Hazards:** Coach tip text is not a gate.

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
020 ──► 111 PARTIAL (pairs with 094)
081·083 ──► 112 PARTIAL
070·081 ──► 113 MISSING
100 ──► 114 MISSING
— ──► 115 LIVE
```

**Suggested first execute after PREP Accept:** **PWO-113 alignment gate** (clear MISSING, safety-critical) *or* **PWO-111 send-path redaction audit** (closes PARTIAL with evidence map). 114 waits on 100/092 chain.

---

## 4. Hazards

1. Do not treat coach anti-PK prose as 113 DONE.
2. Path-leak LIVE ≠ secrets redaction LIVE.
3. Safety list surfaces still Max-gated for product fixes that change auth/send semantics beyond docs.

---

## 5. Execute readiness

PREP ready for hub Accept of this docs WO. Product Execute = separate HANDOFF.
