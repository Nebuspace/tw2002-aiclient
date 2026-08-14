# WO-CANON-DRAFT-SESSION-ENGINE-CITATION-DRIFT

**Goal:** Re-pin stale `session/protocol.py` line citations in
`canon/architecture/session-engine.md` Code Divergence (1). Substantive claim
(App `do`/`send` → `actor="app"` via sender; interactive attach →
`actor="human"`) remains accurate — only pinpoint line numbers drifted.

**Depends-on:** none

**Scope:**
- `canon/architecture/session-engine.md` — update the three protocol.py cites
- this WO file

**Out of scope:** any protocol.py / daemon behavior change.

**Accept:**
1. Doc cites `verb == "do"` / `verb == "send"` dispatch lines that currently
   exist (tip-verified).
2. Doc cites the attach keystroke ledger path that tags `actor="human"`
   (`record_attach_keystroke`), not an unrelated `_record_ledger` docstring.
3. No product code changes.

**Proof:** `rg -n 'protocol.py:' canon/architecture/session-engine.md` matches tip
line numbers under `tw2002_aiclient/session/protocol.py`. Live: n/a (docs-only).
