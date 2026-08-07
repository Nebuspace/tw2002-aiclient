# WO-CANON-DRAFT-TWCLIENT-SESSION-PATH-FRAMING

**Goal:** Remount present-tense `twclient/*` path cites in live architecture concepts to tip
`tw2002_aiclient/session/*` (ADR-001 one-tree).

**Scope:**
- `canon/architecture/resilience-and-reconnect.md` (body + citations)
- `canon/architecture/login-automaton.md` (body + citations)
- `canon/architecture/settle-detection.md` (citations)
- this WO file

**Out of scope:** archive research tables; historical DESIGN-v2 cites; code renames.

**Accept:**
1. Present-tense live cites name `tw2002_aiclient/session/<module>.py` (or `session/<module>.py`).
2. Any remaining `twclient/` in these three files is clearly archive/historical.
3. `suite` green; live-prove `n/a` (docs-only).

**Proof:** grep the three files for `twclient/` → only archive/historical if any.
