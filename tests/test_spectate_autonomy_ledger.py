"""TW-05 real-data autonomy HUD pty proof (hub ticket 2026-07-21).

Proves the shipped WO-P2-d panel (`_autonomy_from_ledger` →
`format_autonomy_lines`) renders AUTO% + App/AI/Hum counts that match a
ledger carrying real `ai`+`trainer` actor rows — the first time that
distribution has been live on disk. Daemon-free FakeClient + pyte
`screen.buffer` cell reads (never ANSI-regex).
"""

from __future__ import annotations

import fcntl
import json
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pyte
import pytest

from twclient.spectate_layout import compute_autonomy_ratio, format_autonomy_counts, format_autonomy_lines

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PTY_ROWS, PTY_COLS = 40, 140  # "full" tier — decisions/GOALS panel present

_SAMPLE_EVENT = {
    "screen": ["Command [TL=00:00:08]:[1234] (?=Help)? :"] + [""] * 23,
    "color": [],
    "prompt": "Command [TL=00:00:08]:[1234] (?=Help)? :",
    "classification": "main_command",
    "settled_reason": "idle",
    "state": {"credits": 100000, "sector": 1027, "turn_timer": "00:00:08", "cargo_holds_empty": 50},
    "ts": "2026-07-21T01:28:45Z",
}

_HARNESS = """
import curses, json, sys, time
sys.path.insert(0, {project_root!r})
from pathlib import Path
from twclient import spectate_app, terminal, ledger

EVENTS = {events}
GAP = 0.25
LEDGER_PATH = Path({ledger_path!r})
ledger.LEDGER_PATH = LEDGER_PATH

class FakeClient:
    def __init__(self, events):
        self._events = events
        self._i = 0
    def next_event(self, timeout=0.1):
        if self._i < len(self._events):
            time.sleep(GAP)
            event = self._events[self._i]
            self._i += 1
            return event
        time.sleep(min(timeout, 0.05))
        return None
    def close(self):
        pass

unicode_ok = terminal.init_locale()
curses.wrapper(
    spectate_app._run, FakeClient(EVENTS),
    Path("/nonexistent/twd-test.sock"), Path("/nonexistent/twd-test.pid"),
    unicode_ok,
)
"""


def _set_winsize(fd, rows, cols):
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _capture_fake_pty(ledger_path: Path, timeout: float = 10.0) -> bytes:
    script = _HARNESS.format(
        project_root=str(PROJECT_ROOT),
        events=json.dumps([_SAMPLE_EVENT]),
        ledger_path=str(ledger_path),
    )
    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, PTY_ROWS, PTY_COLS)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(PROJECT_ROOT), env=env, start_new_session=True,
    )
    os.close(slave_fd)
    captured = b""
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.3)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
                # AUTO line + counts both visible
                if b"AUTO " in captured and b"App " in captured and b"AI " in captured:
                    time.sleep(0.15)  # one extra frame for stability
                    try:
                        while True:
                            ready, _, _ = select.select([master_fd], [], [], 0.05)
                            if master_fd not in ready:
                                break
                            more = os.read(master_fd, 65536)
                            if not more:
                                break
                            captured += more
                    except OSError:
                        pass
                    break
        # detach
        try:
            os.write(master_fd, b"q")
        except OSError:
            pass
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1.0)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.poll() is None:
            proc.kill()
    return captured


def _pyte_screen(captured: bytes) -> pyte.Screen:
    screen = pyte.Screen(PTY_COLS, PTY_ROWS)
    stream = pyte.Stream(screen)
    stream.feed(captured.decode("utf-8", errors="replace"))
    return screen


def _find_text(grid, needle: str):
    for r, row_text in enumerate(grid):
        c = row_text.find(needle)
        if c != -1:
            return r, c
    return None


def _write_swept_style_ledger(path: Path) -> list[dict]:
    """Fixture shaped like the 2026-07-21 crawl_sac sweep: real ai+trainer
    actor rows (session-correlated). Prefer a filtered copy of the live
    ledger when present; otherwise synthesize the same shape.
    """
    live = PROJECT_ROOT / "state" / "ledger.jsonl"
    entries: list[dict] = []
    if live.exists():
        for line in live.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("session_id", "").startswith("20260721T012") and e.get("actor") in (
                "ai",
                "trainer",
            ):
                entries.append(e)
    if not entries:
        # Controlled fallback matching the sweep's actor mix (5 ai + 1 trainer).
        sid = "20260721T012845Z-fixture"
        for _ in range(5):
            entries.append(
                {
                    "ts": "2026-07-21T01:30:00Z",
                    "actor": "ai",
                    "session_id": sid,
                    "input": "D",
                    "prompt": "Command",
                }
            )
        entries.append(
            {
                "ts": "2026-07-21T01:35:00Z",
                "actor": "trainer",
                "session_id": sid,
                "input": "379",
                "prompt": "Command",
            }
        )
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return entries


def test_autonomy_panel_renders_real_ledger_ratio_under_a_fake_pty(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    entries = _write_swept_style_ledger(ledger_path)
    expected = compute_autonomy_ratio(entries)
    auto_line, counts_line = format_autonomy_lines(expected)
    assert expected["trainer"] >= 1 and expected["ai"] >= 1, (
        "fixture must carry both ai and trainer (real-data validation)"
    )

    captured = _capture_fake_pty(ledger_path)
    assert b"AUTO " in captured, (
        f"autonomy AUTO line never rendered; captured (repr first 2k): {captured[:2000]!r}"
    )

    screen = _pyte_screen(captured)
    grid = list(screen.display)

    auto_pos = _find_text(grid, auto_line)
    assert auto_pos is not None, (
        f"{auto_line!r} not in pyte grid (ledger→HUD mismatch). "
        f"expected counts={format_autonomy_counts(expected)!r}; "
        f"grid sample: {[r for r in grid if 'AUTO' in r or 'App' in r]!r}"
    )
    counts_pos = _find_text(grid, counts_line)
    assert counts_pos is not None, (
        f"{counts_line!r} not in pyte grid; AUTO was at {auto_pos}. "
        f"grid sample: {[r for r in grid if 'App' in r or 'AUTO' in r]!r}"
    )

    # Project convention: assert via screen.buffer cells, not ANSI-regex.
    ar, ac = auto_pos
    cell = screen.buffer[ar][ac]
    assert cell.data == auto_line[0], (
        f"screen.buffer[{ar}][{ac}].data={cell.data!r}, expected {auto_line[0]!r}"
    )
    cr, cc = counts_pos
    cell2 = screen.buffer[cr][cc]
    assert cell2.data == counts_line[0]
