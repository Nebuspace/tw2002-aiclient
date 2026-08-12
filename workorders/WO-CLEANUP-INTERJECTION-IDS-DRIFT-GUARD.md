# WO-CLEANUP-INTERJECTION-IDS-DRIFT-GUARD

**Goal:** keep `INTERJECTION_IDS` and `match_interjection`'s return-path ids
from silently drifting.

**Depends-on:** tip `origin/main` at `9e2ef76b` (post #675).

**Scope:**
- `tw2002_aiclient/session/interjection_registry.py` — `_hit()` membership
  check; match paths route through it.
- `tests/test_interjection_registry.py` — AST parity pin.
- `workorders/WO-CLEANUP-INTERJECTION-IDS-DRIFT-GUARD.md` — this file.

**Constraints:**
- Offline cleanup. Do not expand the allow-list or change standing responses.
- Prefer keep the frozenset (exported) + enforce parity; do not delete it.

**Accept:**
- Every id `match_interjection` can return is in `INTERJECTION_IDS`, and every
  frozenset member has a return path (AST parity test).
- Unknown id cannot be returned without failing the `_hit` guard.

**Proof:** `.venv/bin/python -m pytest tests/test_interjection_registry.py -q`;
live-prove `n/a` (offline).

**Refs:** hub queue cycle-52 row · CLAIM `2026-08-12T00:37:15Z`.
