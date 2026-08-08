# WO-BUILD-VERIFY-CANDIDATE-MINING-LANDED

**Goal:** `canon/engine/candidate-mining.md` documents a deterministic
ledger-miner that scans `ledger.jsonl` for repeated keystroke sequences and
emits draft macro proposals into the `_drafts/` promote flow. Re-verified
2026-08-08: `rg candidate_mining|CandidateMin` under `tw2002_aiclient/` is
still zero hits — no matching module/symbol exists under any name (chain
detection in chain_search.py/chain_detect.py is a distinct concept, not
macro-draft mining). Genuinely unbuilt, not a naming mismatch.

**Scope:**
- A module that mines `ledger.jsonl` for repeated keystroke sequences
- Emits draft macro proposals feeding the existing `_drafts/` promote flow
  (do not invent a second promote/approval path — reuse whatever exists)
- Tests covering the mining logic against a synthetic ledger fixture

**Constraints:**
- Offline-only — this reads a persisted ledger file, never sends a live
  keystroke or touches a session
- If the `_drafts/` promote flow's exact shape is unclear, verify it first
  (grep for existing draft/approve/promote machinery) rather than guessing

**Accept:**
- Miner detects repeated sequences in a synthetic ledger fixture and emits
  draft macro proposals in the existing `_drafts/` shape
- Tests pass

**Refs:** canon/engine/candidate-mining.md; 6-lens aiclient audit history (verified-against 2026-08-05, re-verified 2026-08-08)
