# WO-PTY-SETTLE-HYGIENE — Shared mid-flush drain helper · PREP

> Status: **PREP** 2026-07-24 · tip `d2253e9` · seat `impl-aiclient-cursor`  
> Type: PREP only (no product / no helper execute in this WO)  
> **Out:** implementing `settle_drain` · editing any `tests/test_cockpit_*.py` · P3-041 dirty tree · KEY_RESIZE/SIGWINCH execute

## Goal

Inventory the banked mid-flush pty hazard (fixed sleep + one-shot `read` can snapshot a partial curses `refresh()` that spans multiple OS pty chunks) and specify a shared `pty_helpers` settle/drain API so Layer-B drivers stop copying local `_settle` clones.

## Hazard (why this exists)

`PlayShellScreen.draw()` → one `refresh()` still emits **multiple** OS-level pty read chunks. A driver that does `time.sleep(N)` then a **single** `select`+`os.read` can capture mid-flush under CPU contention (stale / truncated chrome). Proven fix pattern (already in-tree, duplicated): keep draining for a wall-time window after the readiness condition.

**Separate follow-on (do not conflate):** live-resize / `KEY_RESIZE` / `SIGWINCH` already has substrate in `tests/pty_helpers.py` (`claim_ctty` / `_claim_controlling_tty` — see `WO-P3-PTY-CTTY.md`). That is **not** this WO’s execute target.

## 1. Inventory — every `tests/test_*_pty.py`

| File | On tip `d2253e9`? | Local `_settle`? | Still sleep + single-read? | Notes |
|---|---|---|---|---|
| `test_cockpit_fold_pty.py` | yes | **yes** | no (uses `_settle` + `ready_text`) | Condition-driven capture (fixture **content**, never bare box title); post-ready `_settle` window |
| `test_cockpit_tones_pty.py` | yes | **yes** | no | Same shape as fold; docstring cites fold/liveness clones |
| `test_cockpit_liveness_pty.py` | yes | **yes** | no | `_settle(1.6)` after ready; clock-file two-capture — sleep is not used to *produce* phase |
| `test_cockpit_hud_pty.py` | yes | **no** | **yes** (`sleep(1.3)` + one `select`/`read`) | **Migrate first** candidate |
| `test_cockpit_goals_pty.py` | yes | **no** | **yes** | Same sleep+single-read pattern as HUD |
| `test_cockpit_focus_pty.py` | yes | **no** | **yes** | Same |
| `test_cockpit_decisions_pty.py` | yes | **no** | **yes** | Same |
| `test_cockpit_frame_pty.py` | yes | **no** | no sleep(1.3); continuous poll until chrome | Lower mid-flush risk than HUD family; still no shared post-ready drain — migrate after HUD/goals/focus/decisions |
| `test_cockpit_logsband_pty.py` | **no** (untracked P3-041 WIP) | **yes** (copied shape) | no | **Defer** until 041 lands on origin — do not edit while parked |
| `test_pty_helpers.py` | yes | n/a | n/a | Unit tests for `pty_helpers` / ctty — not a Layer-B cockpit driver |

Also present in every driver: exit-path drain loop (`drain_deadline` + select/read until poll) — related but **exit hygiene**, not the mid-flush snapshot hazard. Shared helper may optionally wrap both; Accept for execute should prioritize the **post-ready settle** first.

## 2. Proposed shared API (sketch — execute WO owns the real signature)

Prefer one helper next to `_drain_until_exit` in `tests/pty_helpers.py`:

```python
def settle_drain(master_fd: int, captured: bytes, *, seconds: float = 1.3) -> bytes:
    """Drain master_fd for ``seconds`` of wall time, appending to ``captured``.

    Use AFTER a readiness condition (e.g. find_text) so the next ~1 Hz
    refresh fully lands across multi-chunk refreshes. Replaces local
    ``_settle`` clones in fold/tones/liveness and the sleep+single-read
    pattern in hud/goals/focus/decisions.
    """
```

**Composition with `ready_text`:** keep the condition loop in each driver (or a thin `wait_until_text(...)` later); call `settle_drain` only after the condition fires. Do **not** bake fixture-specific ready strings into `pty_helpers`.

**Reuse vs reinvent:** fold/tones/liveness already encode the correct loop — lift that body once; delete per-file `_settle` in the migrate wave.

## 3. Migrate order (execute WO)

1. **Add** `settle_drain` (+ unit pin in `test_pty_helpers.py`: multi-chunk fake writer → single-read fails / settle succeeds).
2. **First drivers (committed suites):** `hud` → `goals` → `focus` → `decisions` (replace sleep+single-read).
3. **Dedup clones:** `fold` → `tones` → `liveness` (delete local `_settle`, import shared).
4. **Optional:** `frame` — add post-ready settle if any flake persists.
5. **Defer:** `logsband` until WO-P3-041 CLOSED on origin.

## 4. Explicitly banked — separate follow-on

| Ticket | Why separate |
|---|---|
| **KEY_RESIZE / SIGWINCH live-resize proofs** | Substrate already in `pty_helpers.claim_ctty` / `WO-P3-PTY-CTTY.md`. Settle-drain does not deliver WINCH; resize tests need ctty + `TIOCSWINSZ`. Do not fold into settle hygiene execute. |

## 5. Accept (for a future EXECUTE WO — not this PREP)

1. `settle_drain` lives in `tests/pty_helpers.py`; hud/goals/focus/decisions no longer use sleep+single-read for post-ready capture.
2. fold/tones/liveness import the shared helper (no local `_settle` duplicate).
3. `logsband` untouched until 041 tip-clean.
4. KEY_RESIZE not claimed done by the settle WO.
5. Scoped commit; path-leak green.

## Refs

- Orch banked after P3-038 Mack (liveness clock seam / mid-flush).
- In-tree clones: `test_cockpit_{fold,tones,liveness}_pty.py` `_settle`.
- Sleep+single-read: `test_cockpit_{hud,goals,focus,decisions}_pty.py`.
- Ctty substrate: `WO-P3-PTY-CTTY.md` · `tests/pty_helpers.py`.
