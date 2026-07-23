# Findings (DOCS-WIN)

**Path choice:** `knowledge/findings.md` (greenfield `knowledge/` created for this file only).
**Nature:** documentation-only. This file **edits no code** and imports nothing from `archive/`.
**Updated:** 2026-07-23 (WO-P0-006).

Central ledger of known **canon ↔ (pre-rebirth / port-source) code** divergences. Under
greenfield rebuild, these are **targets to avoid / correct when reimplementing** — not an
inventory of live root defects (the packages named below lived under
`archive/pre-rebirth-2026-07-23/` and are not imported by the greenfield tree).

---

## Documented divergences (minimum four)

### 1. AI-pilot drive mode (no canon equivalent)

**Canon:** `canon/architecture/control-and-escalation.md` (Code Divergence) — also cross-cited
from `canon/architecture/session-engine.md`.

Pre-rebirth control-lock exposed `MODE_AI_PILOT` / `ai_pilot` as a mode in which "the AI drives."
Reborn north-star / control-and-escalation: live keyboard holders are `{app, human}` only; the AI
is a spectator-teacher that never live-drives. That drive mode has no canon equivalent and must
not return.

### 2. EV-every-tick picker vs stop-on-unknown run-loop

**Canon:** `canon/engine/priority-engine.md` (Code Divergence).

Pre-rebirth shape: `autopilot.select()` scored `run_chain` / `upgrade` / `explore` (etc.) from
scratch every tick — a **per-cycle EV** action-picker. Reborn model: taught-screen APP autopilot
runs known rules/macros and stops on the unknown for the human. Do not revive the EV-every-tick
driver as the live run-loop.

### 3. Legacy live-actor vocabulary vs reborn senders

**Canon:** `canon/architecture/session-engine.md` and `canon/engine/trace-ledger.md` (Code
Divergence sections).

Pre-rebirth `ledger.record_do()` used actor values among `ai` / `trainer` / `human` (default
`"ai"`), treating LLM-decided sends as a live `ai` actor. Reborn send-time invariant: live senders
are `{app, human}` only; AI authorship is provenance of a *rule*, not a ledger live-actor value.
(Phrase for Proof index: actor enum ai trainer human vs app/human.)

### 4. Founding auto-haggle money-path defect

**Canon:** `canon/engine/auto-haggle.md` (Code Divergence — founding auto-haggle finding).

The verified **78-turn**-autopilot money-path misfire is a real defect in the pre-rebirth
auto-haggle / autopilot money path. Reimplementation must treat that finding as a hard regression
target, not an acceptable behavior.

---

## REFERENCE-ONLY — `archive/pre-rebirth-2026-07-23/`

Port-source snapshot only. **Nothing under `archive/` is imported by the greenfield tree.**

Top-level (as of WO-P0-006):

| Path | Note |
|------|------|
| `code/` | Pre-rebirth product packages (`tw2002_aiclient/`, `twclient/`, tests, launchers) |
| `config/` | Pre-rebirth config / secrets layout reference |
| `docs/` | Pre-rebirth operator / design docs |
| `runtime/` | Pre-rebirth runtime artifacts reference |
| `tooling/` | Pre-rebirth tooling |
| `root-misc/` | Misc root leftovers |
| `README.md` | Archive index |

Use for field-shape / behavior reference when a WO explicitly allows it. Never restore to repo root;
never drive recommendations that contradict reborn `canon/`.
