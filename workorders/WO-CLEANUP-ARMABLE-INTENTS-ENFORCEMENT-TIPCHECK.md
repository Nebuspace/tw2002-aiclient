# WO-CLEANUP-ARMABLE-INTENTS-ENFORCEMENT-TIPCHECK

**Goal:** make `ARMABLE_INTENTS` a real Play-arm gate, not a documentation-only
convention list.

**Depends-on:** tip `origin/main` at `9e2ef76` (post #675).

**Scope:**
- `tw2002_aiclient/app.py` — refuse-closed check at explore confirm-arm.
- `tw2002_aiclient/explore.py` — docstring: runtime-enforced at Play arm.
- `tests/test_play_explore_intents.py` — source pin for the membership check.
- `workorders/WO-CLEANUP-ARMABLE-INTENTS-ENFORCEMENT-TIPCHECK.md` — this file.

**Constraints:**
- Do not widen Play's E-cycle; CLI/daemon may still arm the wider `INTENTS`
  set (e.g. `find_formations`).
- Offline; no live TWGS required.

**Accept:**
- Play confirm-arm raises when `armed_intent ∉ ARMABLE_INTENTS`.
- Docstring states the tuple is runtime-enforced there.
- Test pin keeps the check from being deleted silently.

**Proof:** pytest `tests/test_play_explore_intents.py`; live-prove `n/a`.

**Refs:** queue cycle-52 · IDLE-KICK claim `2026-08-12T01:03Z`.
