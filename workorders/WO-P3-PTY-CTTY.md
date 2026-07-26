# WO-P3-PTY-CTTY — Opt-in controlling tty for live-resize pty proofs

> Status: **DONE** · origin `914a0a1` (hub Accept stamp 2026-07-26 · was EXECUTE DONE awaiting Accept)
> Seat: `impl-aiclient-cursor`
> Tip base: `2a2d65c`

## Goal

Banked Mack finding: default `capture_pty*` spawn never claims a controlling
tty → `SIGWINCH` never delivered for future live-resize tests.

## Shipped

`tests/pty_helpers.py`:
- `_claim_controlling_tty(slave_fd)` — `setsid` + `TIOCSCTTY` (raises on ioctl failure)
- `capture_pty` / `capture_pty_with_keys` gain **`claim_ctty: bool = False`**
  - default `False` → `start_new_session=True` (unchanged 030/cockpit behavior)
  - `True` → `preexec_fn` claims ctty so resize tests can get `SIGWINCH`

`tests/test_pty_helpers.py`:
- kwarg default-off contract
- cheap SIGWINCH smoke: `claim_ctty=True` delivers `WINCH`; default path does not

## How resize tests opt in

**Via helpers** (when using `capture_pty*`):

```python
capture_pty(argv, stop, claim_ctty=True, ...)
capture_pty_with_keys(argv, steps, stop, claim_ctty=True, ...)
```

**Via custom Layer-B driver** (own openpty loop — typical for mid-run resize):

```python
from tests.pty_helpers import _claim_controlling_tty, set_winsize

def _preexec():
    _claim_controlling_tty(slave_fd)  # setsid + TIOCSCTTY; do NOT also start_new_session

proc = subprocess.Popen(argv, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                        preexec_fn=_preexec)
# later: set_winsize(master_fd, new_rows, new_cols)  → SIGWINCH in child
```

Default (`claim_ctty=False` / `start_new_session=True`) stays unchanged for 030/cockpit.

## Proof

```bash
.venv/bin/python -m pytest tests/test_pty_helpers.py tests/test_pty_helpers_smoke.py \
  tests/test_play_chrome_nav.py tests/test_cockpit_frame_pty.py -q
```
