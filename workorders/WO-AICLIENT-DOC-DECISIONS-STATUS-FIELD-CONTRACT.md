# WO-AICLIENT-DOC-DECISIONS-STATUS-FIELD-CONTRACT

**Priority:** LOW  
**Claimed-by:** impl-aiclient-h1

## Goal

Name `decisions_status.py` as the documented producer of
`status["autopilot_trace"]` and record its field contract in
`canon/surfaces/trainer-cockpit.md` (pane already covered at render/glyph
level only).

## Changes

- Short **Autopilot-trace producer (field contract)** subsection under the
  right-gutter DECISIONS bullet
- Citations entry for `decisions_status.py` / `cockpit/decisions.py`

## Accept

- [x] Canon names the module as producer
- [x] Fields: `chosen`, `candidates[]` (`kind`, `ev_cr_per_turn`, `gated`,
      `gate_reason`, `rationale`) documented tip-honestly
- [x] Notes FOCUS share + display-only / not-a-keystroke for `chosen`
- live-prove: **n/a** (canon only)

## Proof

```bash
rg -n 'decisions_status|ev_cr_per_turn|Autopilot-trace producer' \
  canon/surfaces/trainer-cockpit.md
```
