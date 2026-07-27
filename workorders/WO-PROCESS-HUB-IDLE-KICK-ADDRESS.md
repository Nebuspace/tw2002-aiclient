# WO-PROCESS-HUB-IDLE-KICK-ADDRESS — Hub self-nudges must not read as spoke directives

**Status:** OPEN · READY · process  
**Posted:** 2026-07-27T20:50:00Z · hub from CC PROCESS-NOTE 20:48:07Z  
**Seat:** hub (Nebuspace `.claude/heartbeat.sh` / coord-monitor)  
**Depends:** none  
**Refs:** CC PROCESS-NOTE · STAR (spokes watch `orchestrator.md` as inbox)

## Goal

Hub HEARTBEAT / IDLE-KICK posts to `orchestrator.md` are every spoke's inbox. Imperative "start idle work NOW / DISCOVERY PASS" without a clear **self-nudge** address causes compliant spokes to nearly (or fully) execute hub duties.

## Spec (pick one, prefer both)

1. Header form: `orchestrator → orchestrator — 💓 HEARTBEAT [self-nudge]` (never bare `orchestrator —`).
2. Body tag line: `**SELF-NUDGE (hub only — spokes ignore for action)**` before any imperative queue/discovery text.
3. Structural (preferred long-term): hub self-kicks append to a file spokes do not watch, **or** coord-monitor spoke path ignores entries tagged self-nudge / `→ orchestrator`.

## Accept

1. A hub IDLE-KICK cannot be mistaken for a HANDOFF to an Implementer without reading the pid.
2. Spoke IDLE-KICK path (own-file) unchanged.
3. PR + STATUS (hub may land in Nebuspace `.claude/`).

## Proof

Docs/script; show before/after sample coord lines. live-prove n/a.
