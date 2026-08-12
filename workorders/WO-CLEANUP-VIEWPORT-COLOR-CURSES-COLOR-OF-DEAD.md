# WO-CLEANUP-VIEWPORT-COLOR-CURSES-COLOR-OF-DEAD

**Status:** IN FLIGHT · impl-aiclient-h1  
**Priority:** LOW  

## Goal

Retire orphaned `cockpit/viewport_color.py::_curses_color_of`. Keep
`PYTE_TO_CURSES_COLOR` (live via `screens.py`).

## Accept

- `_curses_color_of` removed; no product callers remain.
- Tests pin the dict mapping without the wrapper.
- `run_attr` / `align_color_runs` unchanged.

## Proof

```bash
.venv/bin/python -m pytest tests/test_cockpit_viewport_color.py -n0 -q
rg -n '_curses_color_of' tw2002_aiclient tests
```

live-prove: n/a (offline cleanup).
