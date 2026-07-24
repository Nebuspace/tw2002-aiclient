# WO-P3-PTY-CTTY — Opt-in controlling tty for live-resize pty proofs

> Status: **EXECUTE DONE** 2026-07-24 (awaiting hub Accept)
> Seat: `impl-aiclient-cursor`
> Tip base: `2a2d65c`

## Goal

Banked Mack finding: default `capture_pty*` spawn never claims a controlling
tty → `SIGWINCH` never delivered for future live-resize tests.

## Shipped

`tests/pty_helpers.py`:
- `_claim_controlling_tty(slave_fd)` — `setsid` + `TIOCSCTTY`
- `capture_pty` / `capture_pty_with_keys` gain **`claim_ctty: bool = False`**
  - default `False` → `start_new_session=True` (unchanged 030/cockpit behavior)
  - `True` → `preexec_fn` claims ctty so resize tests can get `SIGWINCH`

## How resize tests opt in

```python
from tests.pty_helpers import capture_pty, set_winsize

captured = capture_pty(argv, stop, claim_ctty=True, ...)
# later, from the parent: set_winsize(master_fd, new_rows, new_cols)
```

## Proof

```bash
.venv/bin/python -m pytest tests/test_pty_helpers.py tests/test_pty_helpers_smoke.py \
  tests/test_play_chrome_nav.py tests/test_cockpit_frame_pty.py -q
```
