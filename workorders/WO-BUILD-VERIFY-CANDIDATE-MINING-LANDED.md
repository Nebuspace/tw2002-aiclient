# WO-BUILD-VERIFY-CANDIDATE-MINING-LANDED

**Status:** VERIFIED-LANDED (impl-aiclient-cursor · PR #541)  
**Goal:** `canon/engine/candidate-mining.md` documents a deterministic
ledger-miner that scans `ledger.jsonl` for repeated keystroke sequences and
emits draft macro proposals into the `_drafts/` promote flow. Re-verified
2026-08-08: `rg candidate_mining|CandidateMin` under `tw2002_aiclient/` was
zero hits — **naming miss, not an unbuilt feature.** The engine landed as
`tw2002_aiclient/miner.py` (PWO-095 / #350) with CLI `tw mine` /
`tw patterns` (`mine_cli.py`). This WO tip-verifies Accept and adds a thin
`candidate_mining` facade so future audits resolve the canon name.

**Scope:**
- Tip-verify existing miner → `_drafts/` path (reuse `loops.store.drafts_dir`)
- Thin facade `tw2002_aiclient/candidate_mining.py` (re-export only)
- Tests covering mining against a synthetic ledger fixture (existing + facade pin)

**Constraints:**
- Offline-only — reads a persisted ledger file, never sends a live keystroke
- Do not invent a second promote/approval path — promotion remains the
  skills filesystem gate (`state/skills/_drafts/` → blessed `state/skills/`)

**Accept:**
- [x] Miner detects repeated sequences in a synthetic ledger fixture and emits
  draft macro proposals in the existing `_drafts/` shape
- [x] Tests pass (`tests/test_miner.py`)

**Tip evidence (2026-08-08):**
- Engine: `tw2002_aiclient/miner.py` — `mine_patterns` / `propose_drafts` /
  `mine_ledger` / CLI `__main__`
- Drafts dir: `loops.store.drafts_dir` → `state/skills/_drafts/` (world-scoped
  when `world_id` set)
- Prior WO: `workorders/WO-PWO-095-CANDIDATE-MINING.md` (DONE · #350 · `7788a33`)
- CLI: `tw2002_aiclient/mine_cli.py` (`tw mine` / `tw patterns`)
- Facade (this PR): `tw2002_aiclient/candidate_mining.py` +
  `CandidateMining` alias → `mine_ledger`

**Proof:**
```bash
.venv/bin/python -m pytest tests/test_miner.py -q -n0
```
Live-prove: **n/a** (offline miner; no session/login/play path).

**Refs:** canon/engine/candidate-mining.md; WO-PWO-095-CANDIDATE-MINING;
6-lens aiclient audit history (verified-against 2026-08-05, re-verified 2026-08-08)
