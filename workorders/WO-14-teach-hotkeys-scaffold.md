# WO-14 — Teach hotkeys scaffold (build)
> ⚠️ **LEGACY-SURFACE — non-executable.** Superseded under greenfield rebirth (2026-07-23) by `ULTRACODE-WO-INVENTORY.md` (master list); its Proof paths assume the pre-archive root and will fail. Retained for reference — see the inventory §5 current→proposed mapping for the replacement PWO(s). Do not execute.

**Goal:** Surface A / R / T teach affordances on play control strip as disabled or wired stubs with on-demand-only guardrails.

**Scope:** `tw2002_aiclient/screens.py` control strip · optional thin calls to existing `tw record` / analyze verbs if present

**Depends-on:** WO-13 · WO-10

**Accept:**
- Footer or mode strip shows `A analyze · R record · T assign-trigger` with canon labels
- Keys do not send live game I/O unless backend verb exists and is human-initiated
- `A` never auto-fires (on-demand only — pressing required)
- Unimplemented keys show one-line "not wired" status, not crash

**Proof (TTY):**
```bash
cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
./tw2002-aiclient
# play → press A/R/T → see status feedback, no surprise keystrokes to game
./tw --help | grep -E 'record|analyze'   # document which wire in follow-up WO if missing
```

**Out of scope:** Full AI teacher pipeline · rule approval UI · macro editor.

**Size:** ~1 sitting scaffold.

**Canon:** `canon/surfaces/mode-line-and-teach-controls.md` · `canon/engine/ai-teacher.md` · `macros.md`

**Status:** **Gap** — not present in product TUI.
