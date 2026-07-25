# Implementer brief — OKF screen-pattern reference (Max 2026-07-25)

**To:** `impl-aiclient-cursor` · `impl-claudecode-aiclient`  
**From:** orchestrator  
**Why:** Max directed that useful patterns from the helper + TWGS research passes become
OKF canon, and that Implementers be told explicitly.

## What landed

| Doc | Role |
|---|---|
| [`canon/research/tw2002-screen-patterns.md`](../canon/research/tw2002-screen-patterns.md) | **Required reading** — extracted patterns (P-BLOCK, P-QTY, P-SETTLE-LINE, …) |
| [`canon/index.md`](../canon/index.md) | New **Research / Interop evidence** section |
| Cross-links | Citations on screen-understanding + settle-detection |

Raw research dumps under `research/*-FINDINGS.md` are **superseded** by the OKF extract.
`research/raw/` remains gitignored corpus only — never commit binaries.

## What you must do

1. **Before** any tip that touches `classify.py`, settle/`wait_prompt`, or screen_class vocab:
   read `canon/research/tw2002-screen-patterns.md` end-to-end.
2. Cite the pattern ID (e.g. `P-BLOCK`, `P-SETTLE-LINE`) in your STATUS / WO Accept proof.
3. Honor hard pins already in the extract:
   - **P-QTY:** never auto-answer quantity/money screens; range `[0-20]` ≠ default `[12]`.
   - **P-SETTLE-LINE:** do not treat whole-screen `wait_prompt` hits as live-prompt proof.
   - **P-BANNER:** no regex widen without empirical banner capture.
   - **P-BLOCK:** header/footer titles need not match; exclusivity still required.
4. Closed `screen_class` vocabulary expansions remain **Max-gated** (parked
   `WO-CLASSIFY-BLOCK-TITLES`) — the pattern doc does **not** unilaterally Accept new labels.
5. Do **not** re-mine TWGS installer EXEs (negative result is canon).

## What this is not

- Not a license to expand scope mid-WO.
- Not a substitute for owning-concept Accept bars (screen-understanding / settle-detection).
- Not permission to vendor helper scripts or commit `research/raw/`.

## Ack

Post `🤝 ACK [BRIEF-OKF-SCREEN-PATTERNS]` on your outbox when read. First classify/settle
STATUS after this brief should cite at least one pattern ID.
