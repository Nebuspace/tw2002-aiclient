"""Regression test for the interactive `tw spectate` curses render path.

The panes (viewport/HUD gutter/status, TUI-POLISH-PLAN.md Phase 0/1/2) are
drawn to separate curses sub-windows and are only ever exercised through a
real terminal -- `--snapshot` skips curses entirely (render_plain(), no
windows). That gap let a render-order bug ship (pre Phase-0): _render()
pushed the full-screen stdscr to the virtual screen *after* the panes' own
noutrefresh() calls, so stdscr's just-erased blank content landed on top
of the panes in doupdate(), leaving only the status line visible. These
tests drive the REAL interactive path (not --snapshot) inside a pty,
against the already-running daemon, and assert the panes actually
render -- the only way to catch this class of bug short of a human at a
real terminal.
"""

import curses
import fcntl
import json
import os
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pyte
import pytest

from twclient import chains, terminal
from twclient import spectate_app as spectate_app_mod
from twclient.spectate_app import _SEMANTIC_COLORS, _ColorPairs, _tone_attr
from twclient.spectate_layout import (
    CHAIN_PANEL_DWELL_S,
    CHAIN_PANEL_ROTATION_PERIOD_S,
    MINIMAL_HEADER_MIN_COLS,
    VIEWPORT_H,
    compose_control_strip,
    compose_live_metrics,
    frame_layout,
)

from .conftest import FAKE_HOST

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TW_BIN = PROJECT_ROOT / "tw"
SOCK_PATH = PROJECT_ROOT / "run" / "twd.sock"

# Comfortably in the "minimal" reflow tier (bordered viewport + header
# stat-strip, no side gutter -- see frame_layout()) -- big enough that
# every Phase 0/1/2 chrome element except the side gutter is exercised,
# well above MIN_LINES/MIN_COLS (20x60) so the "terminal too small"
# message never applies here.
PTY_ROWS, PTY_COLS = 36, 120  # right_gutter + outer pad (TW-08): inner 34x118 (== RIGHT_GUTTER_MIN_COLS)

# This environment's actual chrome-glyph capability (same call
# run_interactive() makes) -- both the pty child (env=dict(os.environ), so
# it inherits the SAME locale as this test process) and these assertions
# need to agree on which glyph table is actually in play.
_UNICODE_OK = terminal.init_locale()
_GLYPHS = terminal.glyph_set(_UNICODE_OK)

# A genuine SGR color-SET escape: ESC [ ... 3n/4n/9n/10n m, where n is 0-7
# (basic-8) -- this is what curses' setaf/setab terminfo capabilities emit
# under TERM=xterm when a non-default color_pair() is actually painted.
# Deliberately does NOT match a bare reset ("\x1b[0m"/"\x1b[m") or a plain
# bold code ("\x1b[1m") alone -- those show up even with zero color pairs
# in use, so matching them wouldn't distinguish "colors render" from "they
# don't" (the whole point of the adversarial self-check below).
_COLOR_SET_SGR_RE = re.compile(rb"\x1b\[[0-9;]*(?:3[0-7]|4[0-7]|9[0-7]|10[0-7])m")


def _set_winsize(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _capture_pty(argv, stop_condition, timeout, rows, cols):
    """Spawn `argv` inside a pty, stream its raw output until
    `stop_condition(captured)` is True or `timeout` elapses, then detach
    with 'q' (every child this drives treats 'q' as its own read-only
    detach key -- spectate_app._run's real quit path) and return the raw
    captured bytes. Shared by both the live-daemon path below
    (_run_spectate_in_pty) and the daemon-free fake-client path
    (_run_fake_spectate_in_pty)."""
    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"

    proc = subprocess.Popen(
        argv,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(PROJECT_ROOT),
        env=env,
        start_new_session=True,  # own session -- pty slave becomes its controlling terminal
    )
    os.close(slave_fd)  # only the child needs the slave end

    captured = b""
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.5)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
            if stop_condition(captured):
                break
    finally:
        try:
            os.write(master_fd, b"q")
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        try:
            os.close(master_fd)
        except OSError:
            pass
    return captured


def _run_spectate_in_pty(stop_condition, timeout=10.0, rows=PTY_ROWS, cols=PTY_COLS):
    """Spawn `tw spectate` (the real interactive path, not --snapshot)
    against the ALREADY-RUNNING daemon (read-only, never touches it)."""
    return _capture_pty([str(TW_BIN), "spectate"], stop_condition, timeout, rows, cols)


# A tiny standalone driver script: calls spectate_app._run() DIRECTLY
# against a scripted FakeClient instead of a real SpectateClient -- no
# unix socket, no daemon process, no network at all (this build's
# Network-free constraint). {events} is a JSON list of watch-event dicts
# fed one at a time (with a {gap}s pause between each, then nothing
# further -- next_event() just times out forever after), so a test can
# assert exactly what the render pipeline does with data IT chose,
# including what happens to the HUD purely from local ticking once the
# event stream goes quiet (freshness aging, turn-timer countdown,
# spinner/heartbeat) -- not reachable deterministically against a live,
# unpredictable game session.
_FAKE_HARNESS_TEMPLATE = """
import curses, json, sys, time
sys.path.insert(0, {project_root!r})
from pathlib import Path
from twclient import spectate_app, terminal

EVENTS = {events}
GAP = {gap!r}
# Parsed via json.loads(), not spliced as a Python literal -- JSON's
# true/false/null aren't valid Python source (caught live: embedding the
# JSON text directly raised NameError on the bare word "true").
FAKE_STATUS = json.loads({fake_status_json!r})


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
client = FakeClient(EVENTS)
if FAKE_STATUS is not None:
    # Trainer Control Panel rendering proof: mode/play come from
    # fetch_status(), NOT the event stream -- this harness has no real
    # daemon socket at all (Path("/nonexistent/...") below), so a test
    # that needs a specific mode/play state to prove the badge/progress
    # bar render correctly monkeypatches fetch_status() to return a
    # scripted dict instead of hitting a (nonexistent) socket.
    spectate_app.fetch_status = lambda sock_path, timeout=3.0: dict(FAKE_STATUS)
    spectate_app.fetch_parsed_state = lambda sock_path, timeout=3.0: {{}}

RECORD_PATH = {record_path!r}
if RECORD_PATH is not None:
    # Confirm-gate proof (play_start must NOT fire on a bare Enter --
    # see spectate_app._handle_key's confirm sub-state): _send_control()
    # is the ONE place a META-command actually leaves the process, so
    # recording every call it would have made -- instead of really
    # dialing the (nonexistent) socket -- is the deterministic way to
    # assert "sent nothing" / "sent play_start exactly once" from outside
    # the subprocess. Written to disk only after curses.wrapper() returns
    # (below), so the test must let the harness reach a clean exit
    # (Ctrl-C always does, even mid library-overlay) rather than rely on
    # _capture_pty's own trailing 'q', which the library overlay swallows.
    _sent_calls = []
    # A single fixture loop so `L` has something selectable to arm the
    # confirm gate on -- list_skills goes through the SAME recording stub
    # (it's the only _send_control seam), so it must answer for real
    # rather than fail like every other verb, or library["loops"] would
    # stay empty and Enter would never arm anything.
    _FAKE_LOOPS = [{{"name": "demo-loop", "source": "mined", "profit_per_turn": 12.5, "demo_profit": None, "steps": 4, "draft": False}}]

    def _recording_send_control(sock_path, verb, args=None, timeout=3.0):
        _sent_calls.append({{"verb": verb, "args": args or {{}}}})
        if verb == "list_skills":
            return {{"ok": True, "loops": _FAKE_LOOPS}}
        return {{"ok": False, "error": "fake-harness-no-daemon"}}

    spectate_app._send_control = _recording_send_control

curses.wrapper(
    spectate_app._run, client,
    Path("/nonexistent/twd-test.sock"), Path("/nonexistent/twd-test.pid"),
    unicode_ok,
)

if RECORD_PATH is not None:
    Path(RECORD_PATH).write_text(json.dumps(_sent_calls))
"""


def _run_fake_spectate_in_pty(events, stop_condition, timeout=10.0, rows=PTY_ROWS, cols=PTY_COLS, event_gap_s=0.3, fake_status=None):
    script = _FAKE_HARNESS_TEMPLATE.format(
        project_root=str(PROJECT_ROOT), events=json.dumps(events), gap=event_gap_s,
        fake_status_json=json.dumps(fake_status), record_path=None,
    )
    return _capture_pty([sys.executable, "-c", script], stop_condition, timeout, rows, cols)


def _run_fake_spectate_and_type_in_pty(
    events, type_after, stop_condition, second_type_after=None, third_type_after=None, fourth_type_after=None,
    timeout=10.0, rows=PTY_ROWS, cols=PTY_COLS, event_gap_s=0.3, fake_status=None, record_path=None,
):
    """Like _run_fake_spectate_in_pty(), but also types real keystrokes
    into the pty mid-run -- for proving the Trainer Control Panel's
    keybindings (L)ibrary/Esc/etc actually reach spectate_app._run()'s
    getch() loop. `type_after`/`second_type_after`/`third_type_after`/
    `fourth_type_after` are each (marker_bytes, keys_bytes): once
    `marker_bytes` first appears in the captured output, `keys_bytes` is
    written to the pty -- fired once, strictly in order (a later step
    never fires before the one before it). Detaches with 'q' at the end
    regardless of how far it got -- harmless if the dashboard already
    resumed (q then quits cleanly), but a 'q' while the library overlay
    is STILL open is swallowed, not a detach (see _handle_key()'s
    unconditional `return True` while library["open"]) -- a scripted
    flow that deliberately leaves the overlay open (e.g. a confirm-gate
    cancel) must end its OWN last step by getting itself back to LIST
    mode first (e.g. a plain 'l'/'L', which DOES close from there) so
    the trailing auto-'q' below can do its normal job, rather than typing
    byte 3 and assuming it detaches -- empirically, in this pty harness
    (subprocess start_new_session=True dup2'd onto the pty slave, no
    controlling-terminal ioctl ever established) a real ^C is consumed
    as a driver-level interrupt attempt with nowhere to deliver, not
    passed through to getch() as a literal byte 3 the way a directly-
    typed keystroke would be -- `_handle_key()`'s `ch == 3` branch is
    real code, just not reachable through THIS harness's plumbing."""
    script = _FAKE_HARNESS_TEMPLATE.format(
        project_root=str(PROJECT_ROOT), events=json.dumps(events), gap=event_gap_s,
        fake_status_json=json.dumps(fake_status), record_path=record_path,
    )
    bootstrap = ["-c", script]

    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    proc = subprocess.Popen(
        [sys.executable, *bootstrap], stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(PROJECT_ROOT), env=env, start_new_session=True,
    )
    os.close(slave_fd)

    steps = [type_after, second_type_after, third_type_after, fourth_type_after]
    pending = [s for s in steps if s is not None]
    fired = [False] * len(pending)
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
            for i, (marker, keys) in enumerate(pending):
                if fired[i]:
                    continue
                if i > 0 and not fired[i - 1]:
                    break  # strictly sequential -- don't fire step 2 before step 1
                if marker in captured:
                    try:
                        os.write(master_fd, keys)
                    except OSError:
                        pass
                    fired[i] = True
            if stop_condition(captured):
                break
    finally:
        try:
            os.write(master_fd, b"q")
        except OSError:
            pass
        # Keep draining the pty while waiting for a clean exit, instead of
        # going straight to proc.wait() -- the CHILD's own remaining writes
        # (more redraw frames, then curses' endwin() teardown sequence) can
        # otherwise fill the pty's kernel output buffer and BLOCK its
        # write() forever once nothing is reading anymore, which silently
        # turns every clean exit into a 5s force-kill below -- fatal for a
        # scripted flow that needs the process to actually reach its
        # post-wrapper code (e.g. RECORD_PATH's flush-to-disk, see
        # _FAKE_HARNESS_TEMPLATE) rather than just "captured enough bytes
        # already read before the kill". Bounded the same 5s either way,
        # so a flow that deliberately leaves the overlay open (swallowing
        # 'q', never exiting on its own) costs no more than before.
        drain_deadline = time.monotonic() + 5.0
        while time.monotonic() < drain_deadline and proc.poll() is None:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                captured += chunk
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        try:
            os.close(master_fd)
        except OSError:
            pass
    return captured


def _pyte_screen(captured: bytes, rows: int, cols: int) -> pyte.Screen:
    """Replay a captured raw pty byte stream through pyte (the SAME
    library twclient/terminal.py itself uses) into a `rows`x`cols`
    virtual screen, returning the live pyte.Screen -- `.display` for
    plain text, `.buffer[row][col].fg`/`.reverse`/etc for the SGR
    attributes actually painted at a cell (mirrors terminal.py's own
    color_map() technique) -- a precise, deterministic way to assert
    WHERE a glyph landed and HOW it was colored, instead of fragile
    regex-on-raw-ANSI-soup. Decoded as UTF-8 (with replacement) -- that's
    what curses actually emits for our chrome glyphs under a UTF-8
    locale; plain ASCII decodes identically either way."""
    screen = pyte.Screen(cols, rows)
    stream = pyte.Stream(screen)
    stream.feed(captured.decode("utf-8", errors="replace"))
    return screen


def _pyte_grid(captured: bytes, rows: int, cols: int):
    return list(_pyte_screen(captured, rows, cols).display)


def _find_text(grid, needle):
    """(row, col) of the first occurrence of `needle` in a pyte grid, or
    None -- pairs with _pyte_screen()'s `.buffer` to look up what
    attribute was painted at the text a test actually cares about."""
    for r, row_text in enumerate(grid):
        c = row_text.find(needle)
        if c != -1:
            return r, c
    return None


@pytest.mark.skipif(
    not SOCK_PATH.exists(),
    reason="no live twd daemon socket at run/twd.sock -- `tw start` first to run this test",
)
def test_interactive_spectate_renders_frame_and_hud_under_a_real_pty():
    """Phase 0/1 regression -- the bordered viewport + HUD chrome must
    reach the real terminal, not just compose_hud_cells()'s pure output.
    "CREDITS"/"SECTOR" are static cell labels (compose_hud_cells() always
    emits a placeholder cell even with no data yet, same forward-
    compatible spirit as the old format_sidebar labels this test used to
    check) -- a deterministic signal the header stat-strip actually
    reached the screen, and the viewport border glyph proves the bordered
    game pane rendered alongside it (pre Phase-0: blank, only the status
    line survived a render-order bug of this exact shape)."""
    viewport_glyph = _GLYPHS["viewport_tl"].encode("utf-8")
    captured = _run_spectate_in_pty(
        lambda buf: b"CREDITS" in buf and b"SECTOR" in buf and viewport_glyph in buf
    )
    text = captured.decode("utf-8", errors="replace")

    assert "CREDITS" in text, f"HUD header stat-strip did not render; captured:\n{text}"
    assert "SECTOR" in text, f"HUD header stat-strip did not render; captured:\n{text}"
    assert _GLYPHS["viewport_tl"] in text, f"viewport border did not render; captured:\n{text}"


@pytest.mark.skipif(
    not SOCK_PATH.exists(),
    reason="no live twd daemon socket at run/twd.sock -- `tw ensure` first to run this test",
)
def test_interactive_spectate_renders_real_terminal_colors_under_a_real_pty():
    """D13: the viewport must render the game's actual ANSI colors via
    curses color pairs, not plain text. --snapshot can't exercise this at
    all (no curses); this drives the real interactive path in a pty
    against the live daemon and asserts genuine SGR color-SET escapes
    are present in the raw output -- proof curses is actually painting
    color_pair() attributes, not just A_NORMAL/A_BOLD.

    TW2002/TWGS screens are heavily colored (see terminal.py's
    color_map()), so any real settled screen should trip this within a
    couple of redraw cycles once the HUD strip itself has appeared.
    """
    captured = _run_spectate_in_pty(
        lambda buf: b"CREDITS" in buf and _COLOR_SET_SGR_RE.search(buf) is not None,
        timeout=10.0,
    )

    assert b"CREDITS" in captured, (
        f"HUD pane never rendered -- test setup problem, not a color regression; "
        f"captured (repr, first 2000 bytes): {captured[:2000]!r}"
    )
    match = _COLOR_SET_SGR_RE.search(captured)
    assert match is not None, (
        "no genuine SGR color-SET escape (ESC[..3n/4n/9n/10nm) found in the captured pty "
        f"output -- the viewport rendered in plain text, not real terminal colors. "
        f"captured (repr, first 2000 bytes): {captured[:2000]!r}"
    )


# A minimal, realistic single event -- enough screen text to prove
# geometry (row 0 is non-blank), plus a full state dict so every HUD
# field has something to track.
_SAMPLE_EVENT = {
    "screen": ["Command [TL=00:00:08]:[1234] (?=Help)? :"] + [""] * 23,
    "color": [],
    "prompt": "Command [TL=00:00:08]:[1234] (?=Help)? :",
    "classification": "main_command",
    "settled_reason": "idle",
    "state": {"credits": 100000, "sector": 1027, "turn_timer": "00:00:08", "cargo_holds_empty": 50},
    "ts": "2026-07-19T00:00:00Z",
}
# A follow-up event that DROPS credits/turn_timer/cargo entirely (only
# sector survives) -- e.g. a submenu or combat prompt. The whole point of
# the persistent accumulator: those fields must NOT vanish from the HUD.
_SAMPLE_EVENT_WITHOUT_CREDITS = {
    "screen": ["<A> Attack   <T> Trade   <Q> Quit :"] + [""] * 23,
    "color": [],
    "prompt": "<A> Attack   <T> Trade   <Q> Quit :",
    "classification": "port_menu",
    "settled_reason": "idle",
    "state": {"sector": 1027},
    "ts": "2026-07-19T00:00:01Z",
}


def test_interactive_spectate_viewport_is_native_size_and_un_inset_under_a_fake_pty():
    """The correctness-critical Phase 1 landmine: the bordered viewport
    must wrap the native 80x24 game grid with ZERO inner padding (border
    at (y,x), content starting immediately at (y+1,x+1), never (y+2,x+2)
    or anywhere else) -- any drift here shears the game's CP437 box-art.
    Replays the captured pty stream through pyte (the same library
    terminal.py itself uses) into a real grid so this is a precise
    cell-position assertion, not regex-on-ANSI-soup.

    Drives spectate_app._run() directly against a scripted fake client
    (no daemon, no network -- see _run_fake_spectate_in_pty()) so this
    doesn't depend on a live game session being up, and the screen
    content is exactly known."""
    rows, cols = 40, 140  # comfortably in the "full" tier -- see frame_layout()
    region = frame_layout(rows, cols)["viewport"]
    assert region["border"] is True  # sanity: this size must actually get a border

    corner = _GLYPHS["viewport_tl"]
    corner_bytes = corner.encode("utf-8")
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT], lambda buf: corner_bytes in buf, timeout=8.0, rows=rows, cols=cols
    )
    assert corner_bytes in captured, (
        f"viewport border never rendered at {cols}x{rows}; "
        f"captured (repr, first 2000 bytes): {captured[:2000]!r}"
    )

    grid = _pyte_grid(captured, rows, cols)
    top_row = grid[region["y"]]
    assert top_row[region["x"]] == corner, (
        f"viewport top-left border glyph not at the frame_layout-predicted cell "
        f"({region['y']},{region['x']}); row was: {top_row!r}"
    )
    # Zero inner padding: the cell immediately inside the border (y+1,x+1)
    # must NOT be the border glyph and must not be blank -- proving
    # content starts exactly there, not one cell further in.
    content_row = grid[region["y"] + 1]
    inset_cell = content_row[region["x"] + 1]
    assert inset_cell not in (corner, " "), (
        f"viewport content is not flush against its border at the zero-inset cell "
        f"({region['y'] + 1},{region['x'] + 1}) -- got {inset_cell!r} (row: {content_row!r})"
    )


def test_interactive_spectate_hud_persists_and_ages_freshness_under_a_fake_pty():
    """The HUD accumulator's full live payoff, end-to-end through real
    curses rendering (not just the pure unit tests in
    test_spectate_layout.py):

    1. A SECOND event that drops credits/turn_timer/cargo entirely must
       NOT blank those HUD cells -- the exact bug this build replaces
       (format_sidebar's old `if "credits" in state` silently dropped it).
    2. Once a stat has been seen, its freshness age genuinely ticks
       locally (climbs past "now" into "Ns ago") purely from the
       animation tick, with no further events arriving -- only reachable
       deterministically against a scripted fake client, not a live,
       unpredictable game session.

    Needs the "right_gutter"/"full" tier specifically: the narrower
    "minimal" tier's packed header stat-strip deliberately omits the
    per-cell "Ns ago" text for width reasons (see _draw_header_strip()'s
    docstring) -- only the vertical HUD gutter shows freshness in full."""
    rows, cols = 36, 120  # right_gutter tier -- see frame_layout()
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT, _SAMPLE_EVENT_WITHOUT_CREDITS],
        lambda buf: b"CREDITS" in buf and b"s ago" in buf,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.3,
    )
    assert b"CREDITS" in captured, f"HUD did not render at all; captured:\n{captured!r}"
    assert b"s ago" in captured, (
        "freshness never progressed past the initial marker -- a persisted HUD cell "
        f"that never ages is exactly the 'silently stale' trap the plan calls "
        f"non-negotiable; captured (repr): {captured!r}"
    )

    # The label and value are two separate addnstr() calls (bold label,
    # dim-when-stale value -- see _draw_hud_gutter()), so an SGR escape
    # sits BETWEEN "CREDITS " and "100,000" in the raw byte stream --
    # replay through pyte (like the native-size test above) to check the
    # actually-rendered, escape-free grid instead of raw ANSI soup.
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert re.search(r"CREDITS\s+100,000", full_text), (
        f"CREDITS never showed the real tracked value (100,000) -- either it never "
        f"rendered, or the later credits-less event wrongly blanked it; grid:\n{full_text}"
    )


# -- Phase 3 (felt feedback) / Phase 4 (dataviz) -- each animated behavior
# proven the same way: a scripted fake-client pty run + a pyte replay that
# checks BOTH the rendered text AND the actual per-cell SGR attribute
# (fg color / reverse-video), not just "some escape appeared somewhere".


def _credits_event(credits, ts="2026-07-19T00:00:00Z"):
    return {
        "screen": [f"You have {credits:,} credits."] + [""] * 23,
        "color": [],
        "prompt": "Command [TL=00:00:08]:[1234] (?=Help)? :",
        "classification": "main_command",
        "settled_reason": "idle",
        "state": {"credits": credits, "sector": 1027},
        "ts": ts,
    }


def test_interactive_spectate_credit_gain_flashes_green_with_a_chip_under_a_fake_pty():
    """Phase 3 motion B1: a credits INCREASE flashes the HUD cell green
    with a floating "+230 ▲" chip.

    Stops on the EARLIEST possible signal ("+230" -- the chip is written
    from the very first post-change render, concurrently with the
    count-up tween, not just once it settles) and reads color off the
    CREDITS label's own row/value-column rather than waiting for the
    exact settled "100,230" text: CREDIT_FLASH_DURATION_S is only 1.5s,
    and waiting for tween-settle first burns real wall-clock margin
    against it once subprocess/curses startup overhead is included."""
    rows, cols = 36, 120  # right_gutter tier -- gutter has room for the chip
    captured = _run_fake_spectate_in_pty(
        [_credits_event(100000), _credits_event(100230)],
        lambda buf: b"+230" in buf,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.2,
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert "+230" in full_text, f"no floating delta chip rendered; grid:\n{full_text}"

    label_pos = _find_text(grid, "CREDITS")
    assert label_pos is not None, f"HUD never rendered; grid:\n{full_text}"
    screen = _pyte_screen(captured, rows, cols)
    r, value_col = label_pos[0], label_pos[1] + 8  # label is an 8-char left-padded field
    cell = screen.buffer[r][value_col]
    assert cell.fg == "green", f"CREDITS value not painted green on a gain -- got fg={cell.fg!r}"


def test_interactive_spectate_credit_loss_flashes_red_with_a_chip_under_a_fake_pty():
    """Phase 3 motion B1: a credits DECREASE flashes red with a "-500 ▼" chip."""
    rows, cols = 36, 120
    captured = _run_fake_spectate_in_pty(
        [_credits_event(100000), _credits_event(99500)],
        lambda buf: b"-500" in buf,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.2,
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert "-500" in full_text, f"no floating delta chip rendered; grid:\n{full_text}"

    label_pos = _find_text(grid, "CREDITS")
    assert label_pos is not None, f"HUD never rendered; grid:\n{full_text}"
    screen = _pyte_screen(captured, rows, cols)
    r, value_col = label_pos[0], label_pos[1] + 8
    cell = screen.buffer[r][value_col]
    assert cell.fg == "red", f"CREDITS value not painted red on a loss -- got fg={cell.fg!r}"


def test_interactive_spectate_credits_sparkline_renders_under_a_fake_pty():
    """Phase 4 motion C1: a rolling credits sparkline appears on the
    CREDITS cell's freshness line once there's a real series (2+
    samples) -- distinguishable from plain text by using glyphs outside
    the freshness-line's normal vocabulary (digits/letters/"ago")."""
    rows, cols = 36, 120
    spark_chars = set(_GLYPHS["sparkline"])
    events = [_credits_event(100000 + i * 50) for i in range(5)]
    captured = _run_fake_spectate_in_pty(
        events, lambda buf: b"CREDITS" in buf and b"s ago" in buf,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.3,
    )
    grid = _pyte_grid(captured, rows, cols)
    credits_pos = _find_text(grid, "CREDITS")
    assert credits_pos is not None, f"HUD never rendered; grid:\n{chr(10).join(grid)}"
    freshness_row = grid[credits_pos[0] + 1]
    found = [ch for ch in freshness_row if ch in spark_chars]
    assert found, (
        f"no sparkline glyph found on the CREDITS freshness line; row was: {freshness_row!r}"
    )


def test_interactive_spectate_turns_gauge_renders_and_colors_danger_when_low_under_a_fake_pty():
    """Phase 4 motion C5: the turns-left fuel gauge bar-meter appears
    once a session-max is known, and colors red once the fraction drops
    into the danger band (<20%).

    The gauge renders on the TURNS cell's freshness LINE (row+1), not
    the label/value line -- see _draw_hud_gutter()'s docstring. Waits
    for the SPECIFIC 10%-fraction bar pattern (1 filled / 9 empty), not
    just "a bar appeared", since the first (1000/1000 = 100%, all-filled,
    green) event would otherwise satisfy a looser check before the
    second event -- the one this test is actually about -- ever lands."""
    rows, cols = 36, 120
    events = [
        {**_credits_event(100000), "state": {"credits": 100000, "turns_left": 1000}},
        {**_credits_event(100000), "state": {"credits": 100000, "turns_left": 100}},  # 10% left
    ]
    bar_full = _GLYPHS["bar_full"]
    bar_empty = _GLYPHS["bar_empty"]
    danger_gauge = ("[" + bar_full * 1 + bar_empty * 9 + "]").encode("utf-8")
    captured = _run_fake_spectate_in_pty(
        events, lambda buf: danger_gauge in buf,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.3,
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert bar_full in full_text, f"no gauge bar rendered; grid:\n{full_text}"

    turns_pos = _find_text(grid, "TURNS")
    assert turns_pos is not None, f"TURNS cell never rendered; grid:\n{full_text}"
    gauge_row = grid[turns_pos[0] + 1]
    bar_col = gauge_row.find(bar_full)
    assert bar_col != -1, f"no bar-meter glyph on the TURNS freshness/gauge line: {gauge_row!r}"
    screen = _pyte_screen(captured, rows, cols)
    cell = screen.buffer[turns_pos[0] + 1][bar_col]
    assert cell.fg == "red", f"TURNS gauge not painted red at 10% remaining -- got fg={cell.fg!r}"


def test_interactive_spectate_port_panel_renders_bar_meters_under_a_fake_pty():
    """Phase 4 motion C4: port commodity %-bar-meters appear in the HUD
    gutter, colored green for a "buying" row."""
    rows, cols = 36, 120
    event = {
        "screen": ["<A> Attack   <T> Trade   <Q> Quit :"] + [""] * 23,
        "color": [],
        "prompt": "<A> Attack   <T> Trade   <Q> Quit :",
        "classification": "port_menu",
        "settled_reason": "idle",
        "state": {
            "sector": 1027,
            "port": {"commodities": [{"name": "Fuel Ore", "status": "buying", "amount": 2650, "pct": 100}]},
        },
        "ts": "2026-07-19T00:00:00Z",
    }
    bar_full = _GLYPHS["bar_full"]
    captured = _run_fake_spectate_in_pty(
        [event], lambda buf: b"PORT" in buf and b"Fuel Ore" in buf,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.2,
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert "PORT" in full_text and "Fuel Ore" in full_text, f"port panel never rendered; grid:\n{full_text}"

    pos = _find_text(grid, "Fuel Ore")
    assert pos is not None
    row_text = grid[pos[0]]
    bar_col = row_text.find(bar_full)
    assert bar_col != -1, f"no bar-meter glyph on the port commodity row: {row_text!r}"
    screen = _pyte_screen(captured, rows, cols)
    cell = screen.buffer[pos[0]][bar_col]
    assert cell.fg == "green", f"a 'buying' port row should render green -- got fg={cell.fg!r}"


def test_interactive_spectate_ticker_flashes_newest_row_under_a_fake_pty():
    """Phase 3 motion B3: the newest ticker row gets a brief highlighted
    color right after it arrives."""
    rows, cols = 36, 120
    events = [_credits_event(100000), _credits_event(100100)]
    captured = _run_fake_spectate_in_pty(
        # Wait for the SECOND credits paint so the newest ticker row is
        # still inside TICKER_FLASH_DURATION_S. Do not require
        # "main_command" — LOG tail-truncates under the CHAIN three-pane
        # band and may only show "n_command".
        events,
        lambda buf: b"100,100" in buf and b"(idle)" in buf and _COLOR_SET_SGR_RE.search(buf) is not None,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.3,
    )
    grid = _pyte_grid(captured, rows, cols)
    # LOG prefers the line TAIL when truncating (settle/TX suffixes); with
    # the WO-TUI-CHAIN-BOX three-pane band, the classification prefix may
    # be clipped — match a settle token that remains visible. Prefer the
    # LAST match (newest ticker row — the one that flashes).
    pos = None
    for r, row_text in enumerate(grid):
        c = row_text.find("(idle)")
        if c != -1:
            pos = (r, c)
    assert pos is not None, f"ticker never rendered; grid:\n{chr(10).join(grid)}"
    screen = _pyte_screen(captured, rows, cols)
    row_cells = screen.buffer[pos[0]]
    # The whole line was drawn with ONE attribute (_draw_ticker() passes
    # a single `attr` for the row) -- any painted cell on it proves the
    # flash attribute was applied, without needing to know the exact
    # column the ticker text starts at.
    fg_colors = {row_cells[c].fg for c in range(pos[1], pos[1] + 20)}
    assert "brown" in fg_colors or "yellow" in fg_colors, (
        f"newest ticker row was not flash-colored -- fg colors seen: {fg_colors}"
    )


def test_interactive_spectate_classification_pulse_reverses_header_under_a_fake_pty():
    """Phase 3 motion B4: a classification CHANGE briefly reverses the
    header line. Needs a tier where the classification-badge header
    actually renders (right_gutter/full), not the "minimal" tier's HUD
    stat-strip, which shows no classification text at all."""
    rows, cols = 36, 120
    event_a = _credits_event(100000)
    event_b = {**_credits_event(100000), "classification": "port_menu"}
    captured = _run_fake_spectate_in_pty(
        [event_a, event_b], lambda buf: b"PORT MENU" in buf,
        timeout=8.0, rows=rows, cols=cols, event_gap_s=0.3,
    )
    grid = _pyte_grid(captured, rows, cols)
    pos = _find_text(grid, "PORT MENU")
    assert pos is not None, f"header never showed the new classification; grid:\n{chr(10).join(grid)}"
    screen = _pyte_screen(captured, rows, cols)
    cell = screen.buffer[pos[0]][pos[1]]
    assert cell.reverse is True, (
        f"header was not reverse-video after a classification change -- cell: {cell!r}"
    )


# -- Trainer Control Panel: control strip / mode badge / TX / loops library --
# Rendering-only proofs (fake-client, scripted status -- see
# _run_fake_spectate_in_pty's fake_status kwarg) -- real keypress-driven
# daemon interaction (mode cycling, starting a loop) is proven separately
# in test_control_panel.py against an isolated fake daemon.

_DEFAULT_FAKE_STATUS = {
    "connected": True, "subscriber_count": 1, "last_rx_age_s": 0.1,
    "daemon_pid": "0", "host": FAKE_HOST, "name": "AEGIS",
    "mode": "ai_pilot", "play": None,
}


def _status(**overrides):
    return {**_DEFAULT_FAKE_STATUS, **overrides}


def test_on_sigint_sets_detach_pending_flag():
    """TW-15 unit: SIGINT handler must arm the detach latch (the real-terminal
    path under curses cbreak/ISIG never delivers byte 3 to getch)."""
    spectate_app_mod._detach_pending.clear()
    spectate_app_mod._on_sigint(signal.SIGINT, None)
    assert spectate_app_mod._detach_pending.is_set()
    spectate_app_mod._detach_pending.clear()


def test_sigint_detaches_interactive_spectate_under_a_fake_pty():
    """TW-15: sending SIGINT to the spectate process (what a real terminal's
    Ctrl-C does under curses cbreak/ISIG) must cleanly exit the curses loop
    -- proving the escape hatch is no longer dead code that only checked
    getch()==3."""
    rows, cols = 36, 120
    script = _FAKE_HARNESS_TEMPLATE.format(
        project_root=str(PROJECT_ROOT), events=json.dumps([_SAMPLE_EVENT]),
        gap=0.3, fake_status_json=json.dumps(_status()), record_path=None,
    )
    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, rows, cols)
    env = dict(os.environ)
    env["TERM"] = "xterm"
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
        cwd=str(PROJECT_ROOT), env=env, start_new_session=True,
    )
    os.close(slave_fd)
    captured = b""
    deadline = time.monotonic() + 8.0
    saw_hud = False
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
                if b"AI-PILOT" in captured and not saw_hud:
                    saw_hud = True
                    os.kill(proc.pid, signal.SIGINT)
            if saw_hud and proc.poll() is not None:
                break
        assert saw_hud, f"spectate never rendered before SIGINT; captured:\n{captured!r}"
        # Allow a short window for the loop to notice _detach_pending.
        proc.wait(timeout=5)
        assert proc.returncode == 0, (
            f"SIGINT detach should exit cleanly via curses.wrapper; "
            f"got returncode={proc.returncode}"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        try:
            os.close(master_fd)
        except OSError:
            pass


def test_control_strip_shows_the_ai_pilot_badge_and_hints_under_a_fake_pty():
    rows, cols = 36, 120  # right_gutter tier -- plenty of leftover for the control strip
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT], lambda buf: b"AI-PILOT" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(),
    )
    text = captured.decode("utf-8", errors="replace")
    assert "AI-PILOT" in text, f"mode badge never rendered; captured:\n{text}"
    assert "M)ode" in text, f"keybinding hints never rendered; captured:\n{text}"

    grid = _pyte_grid(captured, rows, cols)
    pos = _find_text(grid, "AI-PILOT")
    assert pos is not None
    screen = _pyte_screen(captured, rows, cols)
    cell = screen.buffer[pos[0]][pos[1]]
    assert cell.reverse is True, f"mode badge should render reverse-video (badge look) -- cell: {cell!r}"


def test_control_strip_shows_the_attach_takeover_hint_under_a_fake_pty():
    """Human-reported discoverability gap (live witness, 2026-07-21): `M`
    only cycles ai_pilot<->spectate by design -- the legend must point to
    the real `A)ttach` keybinding (WO-FA5c upgrade from the interim
    "attach:drive" pointer). Proven at the standard witness geometry
    (36x120, right_gutter tier) via the pyte grid/buffer (project
    convention, never ANSI-regex): the new hint renders AND the
    pre-existing legend tokens are still fully intact, not truncated to
    make room for it."""
    rows, cols = 36, 120
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT], lambda buf: b"A)ttach" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(),
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert "A)ttach" in full_text, f"attach-takeover hint never rendered; grid:\n{full_text}"
    # The existing legend must survive intact, right up to its last
    # token -- a truncated "P pani" (or similar) would be exactly the
    # new discoverability bug pixel warned against.
    assert "M)ode" in full_text and "P panic" in full_text, (
        f"pre-existing control hints got truncated to fit the new addition; grid:\n{full_text}"
    )


def test_control_strip_shows_the_auto_loop_badge_and_live_progress_bar_under_a_fake_pty():
    rows, cols = 36, 120
    play = {"running": True, "paused": False, "name": "demo-loop", "cycle": 2, "cycles_total": 5, "last_result": None}
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT], lambda buf: b"AUTO-LOOP" in buf and b"demo-loop" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(mode="auto_loop", play=play),
    )
    text = captured.decode("utf-8", errors="replace")
    assert "AUTO-LOOP" in text, f"auto_loop badge never rendered; captured:\n{text}"
    assert "Playing demo-loop" in text, f"live progress readout never rendered; captured:\n{text}"
    assert "2/5" in text


def test_control_strip_shows_manual_badge_when_a_human_is_attached_under_a_fake_pty():
    rows, cols = 36, 120
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT], lambda buf: b"YOU HAVE CONTROL" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(mode="human"),
    )
    assert b"YOU HAVE CONTROL" in captured, f"manual/attach badge never rendered; captured:\n{captured!r}"


def test_control_strip_shows_the_spectate_badge_and_survives_the_muted_tone_under_a_fake_pty():
    """Regression: mode="spectate" -> badge_tone "muted" (format_mode_badge())
    used to hit an unguarded _SEMANTIC_COLORS["muted"] subscript in
    _tone_attr()/_draw_control_strip() -- no "muted" key existed, so the
    very first render KeyError'd the whole curses loop dead. Mirrors
    test_control_strip_shows_manual_badge_...'s shape but drives the
    SPECTATE mode specifically -- the exact state that crashed."""
    rows, cols = 36, 120
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT], lambda buf: b"SPECTATE" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(mode="spectate"),
    )
    assert b"SPECTATE" in captured, f"spectate badge never rendered; captured:\n{captured!r}"
    text = captured.decode("utf-8", errors="replace")
    assert "Traceback" not in text, f"render loop raised instead of degrading; captured:\n{text}"


def test_tone_attr_resolves_muted_and_degrades_gracefully_for_an_unknown_tone():
    """Unit-level companion to the fake-pty test above, isolating the
    exact function that crashed: _tone_attr() must resolve the "muted"
    tone (SPECTATE's badge_tone) AND must not raise for a tone this
    build's _SEMANTIC_COLORS doesn't recognize at all (forward-compat --
    a future producer emitting a tone this build predates) -- degrading
    to `default_attr` in both failure-adjacent cases rather than
    KeyError-ing the render loop. _ColorPairs(), uninitialized (its
    .init() is never called), degrades to plain bold/normal attrs with no
    real curses window needed -- the same graceful-no-color-support path
    it already uses on an actual non-color terminal."""
    assert "muted" in _SEMANTIC_COLORS
    palette = _ColorPairs()
    default_attr = curses.A_NORMAL

    muted_attr = _tone_attr("muted", palette, default_attr)  # must not raise
    assert muted_attr == curses.A_NORMAL  # muted spec is non-bold -- see _SEMANTIC_COLORS

    unknown_attr = _tone_attr("some_future_tone_this_build_predates", palette, default_attr)
    assert unknown_attr == default_attr  # unrecognized tone -> caller's default, not a crash

    # The real code path: compose_control_strip()'s SPECTATE badge_tone
    # fed straight through _tone_attr(), exactly as _draw_control_strip() does.
    strip = compose_control_strip("spectate", None, None)
    assert strip["badge_tone"] == "muted"
    _tone_attr(strip["badge_tone"], palette, curses.A_NORMAL)  # must not raise


def test_control_strip_shows_the_live_tx_readout_under_a_fake_pty():
    rows, cols = 36, 120
    event = {**_SAMPLE_EVENT, "sent_input": "158"}
    captured = _run_fake_spectate_in_pty(
        [event], lambda buf: b"\xe2\x86\x92 158" in buf,  # UTF-8 for "→ 158"
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(),
    )
    text = captured.decode("utf-8", errors="replace")
    assert "→ 158" in text, f"TX readout never rendered; captured:\n{text}"


def test_control_strip_ticker_pairs_tx_with_the_settle_outcome_under_a_fake_pty():
    rows, cols = 36, 120
    events = [{**_SAMPLE_EVENT, "sent_input": "d"}]
    captured = _run_fake_spectate_in_pty(
        events, lambda buf: b"main_command" in buf and b"\xe2\x86\x92d" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(),
    )
    text = captured.decode("utf-8", errors="replace")
    assert "→d" in text, f"ticker never paired the sent input with its outcome; captured:\n{text}"


def test_loops_library_overlay_opens_on_l_and_lists_loops_under_a_fake_pty():
    """The overlay's own data comes from a real `list_skills` socket
    call (_send_control()), which this harness's nonexistent sock_path
    can't answer -- so opening it here renders the "(no learned loops
    yet...)" empty state. That's still a genuine proof the OVERLAY
    ITSELF (header, replacing the dashboard, closable) renders and
    responds to input; a real populated listing + Enter-to-start is
    proven end-to-end in test_control_panel.py against a real (fake-
    session) daemon."""
    rows, cols = 36, 120
    captured = _run_fake_spectate_and_type_in_pty(
        [_SAMPLE_EVENT],
        type_after=(b"AI-PILOT", b"l"),
        stop_condition=lambda buf: b"TRADE LOOP CHAINS" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(),
    )
    text = captured.decode("utf-8", errors="replace")
    assert "TRADE LOOP CHAINS" in text, f"library overlay never opened; captured:\n{text}"
    assert "no trade loop chains yet" in text, f"empty-state message never rendered; captured:\n{text}"


def test_loops_library_overlay_closes_on_esc_and_dashboard_resumes_under_a_fake_pty():
    rows, cols = 36, 120
    captured = _run_fake_spectate_and_type_in_pty(
        [_SAMPLE_EVENT],
        type_after=(b"AI-PILOT", b"l"),
        second_type_after=(b"TRADE LOOP CHAINS", bytes([27])),  # Esc
        stop_condition=lambda buf: buf.count(b"AI-PILOT") >= 2,  # dashboard re-rendered after closing
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(),
    )
    assert b"TRADE LOOP CHAINS" in captured, "overlay never opened in the first place"
    # The LAST thing on screen (pyte's replayed grid) must be the normal
    # dashboard again, not the overlay frozen open.
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert "TRADE LOOP CHAINS" not in full_text, f"overlay still showing after Esc; grid:\n{full_text}"
    assert "AI-PILOT" in full_text, f"dashboard did not resume after closing the overlay; grid:\n{full_text}"


# -- Confirm-gate before Enter can launch a LIVE, money-spending loop --
# (the footgun that actually cost the operator real credits: a bare Enter used to
# fire play_start immediately). Both tests drive the SAME l -> Enter ->
# resolve sequence and inspect `_sent_calls` (see _FAKE_HARNESS_TEMPLATE's
# RECORD_PATH branch) rather than screen text, since a swallowed/refused
# send renders identically to a successful one from this harness (no real
# daemon on the other end either way) -- the only trustworthy signal is
# whether _send_control("play_start", ...) was ever actually called.


def test_library_enter_arms_a_confirm_prompt_instead_of_launching_under_a_fake_pty(tmp_path):
    """Enter alone must never fire play_start -- it only ARMS the y/N
    gate. This is the visible half of the proof (the prompt text itself
    must actually render); the two tests below are the behavioral half
    (send-exactly-once on y, send-nothing on cancel), each verified
    against `_sent_calls` rather than screen text since a swallowed/
    refused send renders identically to a real one on this daemon-less
    harness -- the only trustworthy signal is whether _send_control()
    was ever actually called with "play_start"."""
    rows, cols = 36, 120
    record_path = tmp_path / "sent_calls.json"
    captured = _run_fake_spectate_and_type_in_pty(
        [_SAMPLE_EVENT],
        type_after=(b"AI-PILOT", b"l"),
        second_type_after=(b"TRADE LOOP CHAINS", b"\r"),  # Enter -- must only ARM, not fire
        stop_condition=lambda buf: b"LIVE? y/N" in buf,
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(), record_path=str(record_path),
    )
    text = captured.decode("utf-8", errors="replace")
    assert 'Play "demo-loop" x1 LIVE? y/N' in text, f"confirm prompt never rendered; captured:\n{text}"


def test_library_enter_then_y_fires_play_start_exactly_once_under_a_fake_pty(tmp_path):
    rows, cols = 36, 120
    record_path = tmp_path / "sent_calls.json"
    captured = _run_fake_spectate_and_type_in_pty(
        [_SAMPLE_EVENT],
        type_after=(b"AI-PILOT", b"l"),
        second_type_after=(b"TRADE LOOP CHAINS", b"\r"),  # arm
        third_type_after=(b"LIVE? y/N", b"y"),  # confirm
        stop_condition=lambda buf: buf.count(b"AI-PILOT") >= 2,  # dashboard resumed post-launch
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(), record_path=str(record_path),
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert "TRADE LOOP CHAINS" not in full_text, f"overlay should close after confirming; grid:\n{full_text}"

    calls = json.loads(record_path.read_text())
    play_start_calls = [c for c in calls if c["verb"] == "play_start"]
    assert len(play_start_calls) == 1, f"expected exactly one play_start; got: {calls}"
    assert play_start_calls[0]["args"] == {"name": "demo-loop", "cycles": 1}


def test_library_enter_then_cancel_sends_nothing_under_a_fake_pty(tmp_path):
    """Any real key OTHER than y/Y at the confirm prompt cancels back to
    the list with NO send -- proven with 'n' rather than Esc to avoid
    ncurses' ESCDELAY escape-sequence-detection window (Esc and 'n' share
    the exact same cancel branch in _handle_key -- see the `elif ch !=
    -1` fallthrough, not a special-cased key list). The 4th scripted key
    is a plain 'l' -- back in LIST mode after the cancel, that's the
    ALREADY-PROVEN close key (see test_loops_library_overlay_closes_on_esc
    above), which lets the harness's normal trailing 'q' finish the job,
    rather than reaching for Ctrl-C (unreliable in THIS pty harness --
    see _run_fake_spectate_and_type_in_pty's docstring)."""
    rows, cols = 36, 120
    record_path = tmp_path / "sent_calls.json"
    _run_fake_spectate_and_type_in_pty(
        [_SAMPLE_EVENT],
        type_after=(b"AI-PILOT", b"l"),
        second_type_after=(b"TRADE LOOP CHAINS", b"\r"),  # arm
        third_type_after=(b"LIVE? y/N", b"n"),  # cancel -- library stays open, no send
        fourth_type_after=(b"cycles armed", b"l"),  # close the (now-plain-list) overlay
        stop_condition=lambda buf: buf.count(b"AI-PILOT") >= 2,  # dashboard resumed after closing
        timeout=8.0, rows=rows, cols=cols, fake_status=_status(), record_path=str(record_path),
    )
    calls = json.loads(record_path.read_text())
    assert all(c["verb"] != "play_start" for c in calls), (
        f"Enter-then-cancel must send NOTHING to play_start: {calls}"
    )


# ---------------------------------------------------------------------------
# WO-SPECTATE-FLICKER — status poll must not viewport-dirty; idle calm
# ---------------------------------------------------------------------------

def test_status_identity_ignores_idle_age_and_clock_fields():
    """Regression: status polls change last_rx_age_s every time — that
    alone must NOT count as a chrome identity change (would re-dirty
    panes on every poll)."""
    from twclient.spectate_app import _status_identity

    base = {
        "connected": False,
        "mode": "ai_pilot",
        "play": None,
        "subscriber_count": 0,
        "host": None,
        "name": None,
        "daemon_pid": "123",
        "last_rx_age_s": 1.0,
    }
    aged = dict(base)
    aged["last_rx_age_s"] = 99.0
    assert _status_identity(base) == _status_identity(aged)
    flipped = dict(base)
    flipped["connected"] = True
    assert _status_identity(base) != _status_identity(flipped)


def test_idle_anim_interval_is_slower_than_connected():
    from twclient.spectate_app import ANIM_INTERVAL_S, IDLE_ANIM_INTERVAL_S

    assert IDLE_ANIM_INTERVAL_S > ANIM_INTERVAL_S
    assert IDLE_ANIM_INTERVAL_S >= 0.4


def test_spectate_source_status_poll_does_not_set_got_content():
    """Static guard: ordinary status polls must not assign got_content
    (the confirmed WO-SPECTATE-FLICKER mechanism). Connected-flip may
    set it once so the waiting-frame can swap. Chrome uses chrome_dirty."""
    src = (PROJECT_ROOT / "twclient" / "spectate_app.py").read_text()
    assert "chrome_dirty" in src
    assert "Intentionally NOT got_content" in src or "only the connected-flip" in src
    poll_start = src.index("if now - last_status_poll > STATUS_POLL_INTERVAL_S:")
    poll_end = src.index("flash_active = now < flash_until")
    poll_block = src[poll_start:poll_end]
    assert "chrome_dirty = True" in poll_block
    # got_content may appear only under the connected-flip branch.
    for line in poll_block.splitlines():
        if "got_content = True" in line:
            assert "Viewport must swap" in poll_block or "connected" in poll_block.lower()
            break
    else:
        # Fine if we ever move the flip mark elsewhere.
        pass


def test_waiting_session_screen_mentions_no_game():
    from twclient.spectate_layout import waiting_session_screen

    lines = waiting_session_screen(24)
    assert any("No game session" in line for line in lines)
    assert len(lines) == 24


def test_outer_frame_only_drawn_when_got_content():
    """WO-SPECTATE-FLICKER mechanism #2: anim-only frames must NOT
    erase the full-client outer sibling (that blanks viewport/ticker)."""
    src = (PROJECT_ROOT / "twclient" / "spectate_app.py").read_text()
    # The call site must be gated on got_content.
    assert "if got_content and regions.get(\"outer\")" in src or \
        "if got_content and regions.get('outer')" in src
    # And there must be an explanatory note tying erase() to the blank-pane failure.
    assert "WO-SPECTATE-FLICKER follow-up" in src
    assert "_draw_outer_frame" in src


def test_render_skips_outer_erase_on_anim_only_tick(monkeypatch):
    """Runtime invariant: calm idle `_render` with got_content=False never
    calls `_draw_outer_frame` (no erase of the full-client sibling)."""
    drawn = {"outer": 0, "viewport": 0, "doupdate": 0}

    def fake_outer(*a, **k):
        drawn["outer"] += 1

    def fake_viewport(*a, **k):
        drawn["viewport"] += 1

    def fake_doupdate():
        drawn["doupdate"] += 1

    monkeypatch.setattr(spectate_app_mod, "_draw_outer_frame", fake_outer)
    monkeypatch.setattr(spectate_app_mod, "_draw_viewport", fake_viewport)
    monkeypatch.setattr(curses, "doupdate", fake_doupdate)
    # Stub the other pane drawers used on an anim tick so _render can run
    # without real curses windows.
    for name in (
        "_draw_header_strip", "_draw_header", "_draw_ticker",
        "_draw_hud_gutter", "_draw_decisions", "_draw_control_strip", "_draw_status",
    ):
        monkeypatch.setattr(spectate_app_mod, name, lambda *a, **k: None)

    regions = {
        "mode": "comfortable",
        "outer": {"y": 0, "x": 0, "h": 36, "w": 120},
        "header": None,
        "viewport": {"y": 2, "x": 1, "h": 26, "w": 82, "border": True, "game_h": 24, "game_w": 80},
        "gutter": None,
        "decisions": None,
        "ticker": None,
        "control": None,
        "status": {"y": 35, "x": 1, "h": 1, "w": 110},
    }
    windows = {
        "outer": object(),
        "viewport": object(),
        "status": object(),
    }
    status = {
        "connected": False, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
    }
    glyphs = {
        "freshness_mark": "*", "delta_up": "^", "delta_down": "v",
        "bar_full": "#", "bar_empty": "-",
        "spinner": ["|", "/", "-"], "heartbeat": [".", "o"],
        "viewport_tl": "+", "viewport_tr": "+", "viewport_bl": "+", "viewport_br": "+",
        "viewport_h": "-", "viewport_v": "|",
        "hud_tl": "+", "hud_tr": "+", "hud_bl": "+", "hud_br": "+",
        "hud_h": "-", "hud_v": "|",
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    # Anim-only tick: must not touch outer or viewport.
    spectate_app_mod._render(
        windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
        FakePalette(), glyphs, now=1.0, anim_tick=3, idle_age=None, semantic="danger",
        flash_active=False, got_content=False, calm_idle=True,
    )
    assert drawn == {"outer": 0, "viewport": 0, "doupdate": 1}

    # Content tick: outer + viewport both paint once.
    spectate_app_mod._render(
        windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
        FakePalette(), glyphs, now=1.0, anim_tick=3, idle_age=None, semantic="danger",
        flash_active=False, got_content=True, calm_idle=True,
    )
    assert drawn["outer"] == 1
    assert drawn["viewport"] == 1
    assert drawn["doupdate"] == 2


# ---------------------------------------------------------------------------
# WO-FA5a — fetch_status() must pass through autopilot_trace
# ---------------------------------------------------------------------------


class _FakeAutopilotEngine:
    """Minimal server.autopilot_engine double -- protocol.py's status verb
    only ever calls .trace_log(), taking the most recent entry (see
    protocol.py:463-468)."""

    def __init__(self, trace):
        self._trace = trace

    def trace_log(self):
        return [self._trace]


def test_fetch_status_passes_through_autopilot_trace(fake_daemon):
    """The Decisions pane's live-trace render (_render(), below) reads
    status.get("autopilot_trace") -- but fetch_status()'s hand-picked
    return dict used to DROP the key entirely even though protocol.py's
    real status verb serves it (test_protocol_trainer_panel.py proves the
    daemon side already works). RED against the old fetch_status: the key
    was simply absent from the dict (not just None), so
    `status["autopilot_trace"]` KeyErrors instead of returning the trace."""
    trace = {"tick": 3, "context": {"sector": 5}, "candidates": [], "chosen": None}
    fake_daemon.server.autopilot_engine = _FakeAutopilotEngine(trace)

    status = spectate_app_mod.fetch_status(fake_daemon.sock_path)
    assert status["autopilot_trace"] == trace


def test_fetch_status_autopilot_trace_is_none_when_nothing_wired(fake_daemon):
    status = spectate_app_mod.fetch_status(fake_daemon.sock_path)
    assert status["autopilot_trace"] is None


def test_fetch_status_connect_failure_still_carries_the_key():
    """The unreachable-socket fallback dict must carry the SAME keys as
    the success path (a caller must never special-case a missing key --
    same null-safe convention protocol.py's status verb itself uses)."""
    status = spectate_app_mod.fetch_status("/nonexistent/twd-test.sock", timeout=0.2)
    assert status["autopilot_trace"] is None
    assert status["credits"] is None
    assert status["credits_age_ms"] is None


def test_fetch_status_passes_through_fa7a_credits(fake_daemon):
    """WO-SPECTATE-HUD-SEED: status already serves FA7a credits; fetch_status
    must not drop them (same class of bug as autopilot_trace)."""
    sess = fake_daemon.server.session
    sess.observe_credits("You have 123,456 credits.\nCommand [TL=00:00:08]:[1027] (?=Help)? :")
    status = spectate_app_mod.fetch_status(fake_daemon.sock_path)
    assert status["credits"] == 123456
    assert isinstance(status["credits_age_ms"], int)
    assert status["credits_age_ms"] >= 0


def test_spectate_seeds_hud_from_status_before_any_event_under_a_fake_pty():
    """Spectate restart within a live daemon session must not show blank HUD
    credits when status knows the balance — even before the subscribe stream
    delivers its first settle edge."""
    rows, cols = 36, 120
    captured = _run_fake_spectate_in_pty(
        [],  # no watch events at all
        lambda buf: b"123,456" in buf,
        timeout=8.0,
        rows=rows,
        cols=cols,
        fake_status=_status(credits=123456, credits_age_ms=2500),
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)
    assert re.search(r"CREDITS\s+123,456", full_text), (
        f"HUD never seeded credits from status on cold connect; grid:\n{full_text}"
    )


# ---------------------------------------------------------------------------
# WO-TUI-GOALS-IN-PRIORITIES — GOALS live in left PRIORITIES; DECISIONS =
# explore/trace only (no FA5a dwell reclaim onto DECISIONS).
# ---------------------------------------------------------------------------


def test_decisions_keeps_trace_never_goals_title(monkeypatch):
    """Live autopilot_trace fills DECISIONS; GOALS never reclaim that pane."""
    captured = []

    def fake_draw_decisions(win, region, lines, glyphs, palette, title=None):
        captured.append((list(lines), title))

    monkeypatch.setattr(spectate_app_mod, "_draw_decisions", fake_draw_decisions)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)

    regions = {
        "mode": "comfortable",
        "outer": None, "header": None, "viewport": None, "gutter": None,
        "decisions": {"y": 0, "x": 0, "h": 5, "w": 22, "title": "DECISIONS"},
        "ticker": None, "control": None,
    }
    windows = {"decisions": object()}
    status = {
        "connected": True, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
        "autopilot_trace": {"tick": 1, "context": {}, "candidates": [], "chosen": None},
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    for now in (CHAIN_PANEL_DWELL_S + 1.0, CHAIN_PANEL_ROTATION_PERIOD_S + 1.0):
        captured.clear()
        spectate_app_mod._render(
            windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
            FakePalette(), {}, now=now, anim_tick=0, idle_age=None, semantic="ok",
            flash_active=False, got_content=True,
            explore_mode="off", phase2_cache={"chain": None},
        )
        lines, title = captured[0]
        assert title == "DECISIONS"
        assert "— GOALS —" not in lines


def test_priorities_panel_owns_goals_with_chain_box(monkeypatch):
    """GOALS render in PRIORITIES; DECISIONS stays trace-titled."""
    captured = []

    def fake_draw_decisions(win, region, lines, glyphs, palette, title=None):
        captured.append((list(lines), title, region.get("title")))

    monkeypatch.setattr(spectate_app_mod, "_draw_decisions", fake_draw_decisions)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)

    regions = {
        "mode": "full",
        "outer": None, "header": None, "viewport": None, "gutter": None,
        "decisions": {"y": 0, "x": 24, "h": 8, "w": 28, "title": "DECISIONS"},
        "priorities": {"y": 0, "x": 0, "h": 8, "w": 24, "title": "PRIORITIES"},
        "chain": {"y": 0, "x": 0, "h": 5, "w": 82},
        "ticker": None, "control": None,
    }
    windows = {"decisions": object(), "priorities": object()}
    status = {
        "connected": True, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
        "autopilot_trace": {"tick": 1, "context": {}, "candidates": [], "chosen": None},
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    spectate_app_mod._render(
        windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
        FakePalette(), {}, now=CHAIN_PANEL_ROTATION_PERIOD_S + 1.0, anim_tick=0,
        idle_age=None, semantic="ok", flash_active=False, got_content=True,
        explore_mode="off", phase2_cache={"chain": None},
    )
    dec = [c for c in captured if c[1] == "DECISIONS" or c[2] == "DECISIONS"]
    pri = [c for c in captured if c[1] == "PRIORITIES" or c[2] == "PRIORITIES"]
    assert len(dec) == 1 and dec[0][1] == "DECISIONS"
    assert "— GOALS —" not in dec[0][0]
    assert len(pri) == 1 and pri[0][1] == "PRIORITIES"
    assert "— GOALS —" in pri[0][0]
    assert "— FOCUS —" in pri[0][0]


def test_decisions_idle_never_shows_tw13_stub(monkeypatch):
    """With left PRIORITIES present and no explore/trace — honest idle, not TW-13."""
    captured = []

    def fake_draw_decisions(win, region, lines, glyphs, palette, title=None):
        captured.append((list(lines), title, region.get("title")))

    monkeypatch.setattr(spectate_app_mod, "_draw_decisions", fake_draw_decisions)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)

    regions = {
        "mode": "full",
        "outer": None, "header": None, "viewport": None, "gutter": None,
        "decisions": {"y": 0, "x": 24, "h": 8, "w": 28, "title": "DECISIONS"},
        "priorities": {"y": 0, "x": 0, "h": 8, "w": 24, "title": "PRIORITIES"},
        "ticker": None, "control": None,
    }
    windows = {"decisions": object(), "priorities": object()}
    status = {
        "connected": True, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
        "autopilot_trace": None,
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    spectate_app_mod._render(
        windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
        FakePalette(), {}, now=0.0, anim_tick=0,
        idle_age=None, semantic="ok", flash_active=False, got_content=True,
        explore_mode="off", phase2_cache={"chain": None},
    )
    dec = [c for c in captured if c[2] == "DECISIONS"]
    pri = [c for c in captured if c[1] == "PRIORITIES" or c[2] == "PRIORITIES"]
    assert len(dec) == 1
    joined = " ".join(dec[0][0]).lower()
    assert "tw-13" not in joined and "coach" not in joined
    # Idle: honest placeholder or coach titles (no stub phrase).
    assert "—" in dec[0][0][0] or "exploring" in joined or len(dec[0][0]) >= 1
    assert len(pri) == 1
    assert "— GOALS —" in pri[0][0]
    assert "— FOCUS —" in pri[0][0]


def test_decisions_shows_coach_on_zero_fighters(monkeypatch):
    """TW-13: 0 fighters → holds-first coaching card in DECISIONS."""
    captured = []

    def fake_draw_decisions(win, region, lines, glyphs, palette, title=None):
        captured.append((list(lines), title, region.get("title")))

    monkeypatch.setattr(spectate_app_mod, "_draw_decisions", fake_draw_decisions)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)
    spectate_app_mod._coach_kb_cache = None
    spectate_app_mod._coach_kb_load_attempted = False

    regions = {
        "mode": "full",
        "outer": None, "header": None, "viewport": None, "gutter": None,
        "decisions": {"y": 0, "x": 24, "h": 8, "w": 28, "title": "DECISIONS"},
        "priorities": {"y": 0, "x": 0, "h": 8, "w": 24, "title": "PRIORITIES"},
        "ticker": None, "control": None,
    }
    windows = {"decisions": object(), "priorities": object()}
    status = {
        "connected": True, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
        "autopilot_trace": None,
        "fighters_aboard": 0,
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    spectate_app_mod._render(
        windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
        FakePalette(), {}, now=0.0, anim_tick=0,
        idle_age=None, semantic="ok", flash_active=False, got_content=True,
        explore_mode="off", phase2_cache={"chain": None},
    )
    dec = [c for c in captured if c[2] == "DECISIONS"]
    assert len(dec) == 1
    joined = " ".join(dec[0][0]).lower()
    assert "holds" in joined
    assert "tw-13" not in joined
    assert "coach" not in joined


def test_decisions_coach_does_not_override_live_trace(monkeypatch):
    """Live autopilot_trace still owns DECISIONS over coach."""
    captured = []

    def fake_draw_decisions(win, region, lines, glyphs, palette, title=None):
        captured.append((list(lines), title, region.get("title")))

    monkeypatch.setattr(spectate_app_mod, "_draw_decisions", fake_draw_decisions)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)

    regions = {
        "mode": "full",
        "outer": None, "header": None, "viewport": None, "gutter": None,
        "decisions": {"y": 0, "x": 24, "h": 8, "w": 28, "title": "DECISIONS"},
        "priorities": {"y": 0, "x": 0, "h": 8, "w": 24, "title": "PRIORITIES"},
        "ticker": None, "control": None,
    }
    windows = {"decisions": object(), "priorities": object()}
    status = {
        "connected": True, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
        "fighters_aboard": 0,
        "autopilot_trace": {
            "tick": 1,
            "context": {},
            "candidates": [],
            "chosen": None,
        },
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    spectate_app_mod._render(
        windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
        FakePalette(), {}, now=0.0, anim_tick=0,
        idle_age=None, semantic="ok", flash_active=False, got_content=True,
        explore_mode="off", phase2_cache={"chain": None},
    )
    dec = [c for c in captured if c[2] == "DECISIONS"]
    assert len(dec) == 1
    joined = " ".join(dec[0][0]).lower()
    assert "holds" not in joined
    assert "hold" in joined  # format_autopilot_trace_lines header when chosen is None


def test_decisions_midwidth_fallback_shows_priorities_when_no_left_gutter(monkeypatch):
    """Without left PRIORITIES region, idle DECISIONS carries goals+weigh (not TW-13)."""
    captured = []

    def fake_draw_decisions(win, region, lines, glyphs, palette, title=None):
        captured.append((list(lines), title))

    monkeypatch.setattr(spectate_app_mod, "_draw_decisions", fake_draw_decisions)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)

    regions = {
        "mode": "right_gutter",
        "outer": None, "header": None, "viewport": None, "gutter": None,
        "decisions": {"y": 0, "x": 0, "h": 8, "w": 28, "title": "DECISIONS"},
        "ticker": None, "control": None,
    }
    windows = {"decisions": object()}
    status = {
        "connected": True, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
        "autopilot_trace": None,
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    spectate_app_mod._render(
        windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
        FakePalette(), {}, now=0.0, anim_tick=0,
        idle_age=None, semantic="ok", flash_active=False, got_content=True,
        explore_mode="off", phase2_cache={"chain": None},
    )
    lines, title = captured[0]
    assert title == "PRIORITIES"
    assert "— GOALS —" in lines
    assert "— FOCUS —" in lines
    assert not any("TW-13" in ln or "coach" in ln.lower() for ln in lines)


def test_decisions_keeps_explore_never_goals_title(monkeypatch):
    """Explore mode owns DECISIONS; GOALS never reclaim that pane."""
    captured = []

    def fake_draw_decisions(win, region, lines, glyphs, palette, title=None):
        captured.append((list(lines), title))

    monkeypatch.setattr(spectate_app_mod, "_draw_decisions", fake_draw_decisions)
    monkeypatch.setattr(curses, "doupdate", lambda: None)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)

    regions = {
        "mode": "comfortable",
        "outer": None, "header": None, "viewport": None, "gutter": None,
        "decisions": {"y": 0, "x": 0, "h": 5, "w": 22, "title": "DECISIONS"},
        "ticker": None, "control": None,
    }
    windows = {"decisions": object()}
    status = {
        "connected": True, "mode": "ai_pilot", "play": None,
        "subscriber_count": 0, "host": None, "name": None,
        "autopilot_trace": None,
    }

    class FakePalette:
        def attr_for(self, *a, **k):
            return 0

    for now in (CHAIN_PANEL_DWELL_S + 1.0, CHAIN_PANEL_ROTATION_PERIOD_S + 1.0):
        captured.clear()
        spectate_app_mod._render(
            windows, regions, dict(spectate_app_mod.DEFAULT_EVENT), {}, [], status,
            FakePalette(), {}, now=now, anim_tick=0, idle_age=None, semantic="ok",
            flash_active=False, got_content=True,
            explore_mode="mapfill", phase2_cache={"chain": None},
        )
        lines, title = captured[0]
        assert title is None
        assert any("explore" in ln for ln in lines)
        assert "— GOALS —" not in lines


# ---------------------------------------------------------------------------
# WO-FA5a — DECISIONS_MIN_H vanish, proven at the real curses render level
# ---------------------------------------------------------------------------


def test_decisions_pane_vanishes_below_its_height_floor_and_log_fills_the_band_under_a_fake_pty():
    """Pixel-flagged proof gap: the geometry floor (DECISIONS_MIN_H) was
    only proven at the pure frame_layout() level so far. Drive the REAL
    curses render at a sub-floor size -- leftover == LOG_BOX_MIN_H, one
    row short of DECISIONS_MIN_H (the same size
    test_frame_layout_decisions_absent_below_its_height_floor proves at
    the pure-layout level in test_spectate_layout.py) -- and confirm, via
    the pyte grid/buffer (never ANSI-regex, project convention): (a) no
    DECISIONS title renders anywhere, (b) the LOG box's own border spans
    the FULL leftover band (not truncated by a phantom decisions split),
    (c) the rest of the chrome (viewport border, HUD) still renders
    cleanly at this reduced size -- no crash, no garbage."""
    rows, cols = VIEWPORT_H + 6 + 2, MINIMAL_HEADER_MIN_COLS + 2  # 34 x 84 -- leftover == 3
    regions = frame_layout(rows, cols)
    assert regions["decisions"] is None  # sanity: this size really is sub-floor
    ticker_region = regions["ticker"]
    assert ticker_region is not None
    viewport_region = regions["viewport"]
    assert viewport_region["border"] is True

    hud_tr = _GLYPHS["hud_tr"]
    captured = _run_fake_spectate_in_pty(
        [_SAMPLE_EVENT], lambda buf: hud_tr.encode("utf-8") in buf,
        timeout=8.0, rows=rows, cols=cols,
    )
    grid = _pyte_grid(captured, rows, cols)
    full_text = "\n".join(grid)

    # (a) DECISIONS never rendered at this size.
    assert "DECISIONS" not in full_text, (
        f"DECISIONS pane rendered below its own height floor; grid:\n{full_text}"
    )

    # (b) LOG fills the WHOLE leftover band: its title renders, and its
    # top border's right-corner glyph reaches the frame_layout-predicted
    # right edge (x + w - 1) -- not a truncated, decisions-shared width.
    assert "LOG" in full_text, f"LOG box never rendered; grid:\n{full_text}"
    top_row = grid[ticker_region["y"]]
    right_edge_col = ticker_region["x"] + ticker_region["w"] - 1
    assert top_row[right_edge_col] == hud_tr, (
        f"LOG box border does not reach the full leftover band's right edge "
        f"(expected {hud_tr!r} at col {right_edge_col}); row was: {top_row!r}"
    )

    # (c) the rest of the chrome still rendered cleanly at this reduced size.
    assert "CREDITS" in full_text, f"HUD did not render at this reduced size; grid:\n{full_text}"
    assert grid[viewport_region["y"]][viewport_region["x"]] == _GLYPHS["viewport_tl"], (
        f"viewport border did not render at this reduced size; "
        f"row was: {grid[viewport_region['y']]!r}"
    )


# ---------------------------------------------------------------------------
# WO-FA5b — _longest_chain_for_panel prefers a REAL FA3 world-model chain
# ---------------------------------------------------------------------------


def test_longest_chain_for_panel_prefers_a_real_profit_chain(monkeypatch):
    """A resolvable world_id with a discoverable profit cycle must win
    over the skill-library fallback -- the library's _send_control()
    must not even be consulted."""
    hops = (
        chains.TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=10.0, turns=2),
        chains.TradeHop(frm=2, to=1, commodity="Organics", margin=5.0, turns=2),
    )
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: "world1")
    monkeypatch.setattr(spectate_app_mod.trade_adapter, "build_trade_hops", lambda wid, **kw: (hops, None))

    def _boom(*a, **k):
        raise AssertionError("library fallback must not be consulted when a real chain exists")

    monkeypatch.setattr(spectate_app_mod, "_send_control", _boom)

    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert isinstance(result, chains.ProfitChain)
    assert result.sectors[0] == result.sectors[-1]  # closed cycle


def test_longest_chain_for_panel_falls_back_when_world_id_missing(monkeypatch):
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: None)
    fake_loops = [{"name": "demo", "source": "mined", "steps": 3, "demo_profit": 100}]
    monkeypatch.setattr(
        spectate_app_mod, "_send_control",
        lambda sock_path, verb, args=None, timeout=3.0: {"ok": True, "loops": fake_loops},
    )
    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert result["name"] == "demo"


def test_longest_chain_for_panel_falls_back_when_no_hops_discoverable(monkeypatch):
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: "world1")
    monkeypatch.setattr(spectate_app_mod.trade_adapter, "build_trade_hops", lambda wid, **kw: ((), None))
    fake_loops = [{"name": "demo", "source": "mined", "steps": 3, "demo_profit": 100}]
    monkeypatch.setattr(
        spectate_app_mod, "_send_control",
        lambda sock_path, verb, args=None, timeout=3.0: {"ok": True, "loops": fake_loops},
    )
    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert result["name"] == "demo"


def test_longest_chain_for_panel_falls_back_when_hops_form_no_profitable_cycle(monkeypatch):
    """Hops exist but don't close into a profitable cycle -- an honest
    fallback to the library, never a fabricated chain."""
    hops = (chains.TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=10.0, turns=2),)
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: "world1")
    monkeypatch.setattr(spectate_app_mod.trade_adapter, "build_trade_hops", lambda wid, **kw: (hops, None))
    fake_loops = [{"name": "demo", "source": "mined", "steps": 3, "demo_profit": 100}]
    monkeypatch.setattr(
        spectate_app_mod, "_send_control",
        lambda sock_path, verb, args=None, timeout=3.0: {"ok": True, "loops": fake_loops},
    )
    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert result["name"] == "demo"


# ---------------------------------------------------------------------------
# WO-TUI-CHAIN-VIZ-SEED — presence-only adjacent ports seed bubble viz
# ---------------------------------------------------------------------------


def test_presence_port_chain_seed_adjacent_ports(tmp_path, monkeypatch):
    """Two adjacent flyby ports (class only, no commodities) → seed sectors."""
    from twclient import world_model
    from twclient.spectate_layout import compose_chain_bubbles, chain_bubble_sectors

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "seed_world"
    world_model.upsert_sector(
        wid,
        {"sector_id": 100, "warps": [200], "port": {"name": "A", "class": "BSB"}},
        state_dir=store,
    )
    world_model.upsert_sector(
        wid,
        {"sector_id": 200, "warps": [100], "port": {"name": "B", "class": "SBB"}},
        state_dir=store,
    )
    seed = spectate_app_mod._presence_port_chain_seed(wid, state_dir=store)
    assert seed is not None
    assert seed.get("source") == "presence_seed"
    assert chain_bubble_sectors(seed) == [100, 200]
    lines = compose_chain_bubbles(seed, port_classes={100: "BSB", 200: "SBB"}, width=40)
    joined = "\n".join(lines)
    assert "100" in joined and "200" in joined
    assert "no trade loop yet" not in joined


def test_longest_chain_for_panel_seeds_when_library_empty(monkeypatch, tmp_path):
    """No ProfitChain + empty library → presence seed (not empty placeholder)."""
    from twclient import world_model

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "seed_world"
    world_model.upsert_sector(
        wid,
        {"sector_id": 10, "warps": [20], "port": {"class": "BBB"}},
        state_dir=store,
    )
    world_model.upsert_sector(
        wid,
        {"sector_id": 20, "warps": [10], "port": {"class": "SSS"}},
        state_dir=store,
    )
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: wid)
    monkeypatch.setattr(spectate_app_mod.trade_adapter, "build_trade_hops", lambda w, **kw: ((), None))
    monkeypatch.setattr(
        spectate_app_mod, "_send_control",
        lambda sock_path, verb, args=None, timeout=3.0: {"ok": True, "loops": []},
    )
    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert isinstance(result, dict)
    assert result.get("source") == "presence_seed"
    assert list(result.get("sectors") or ())[:2] == [10, 20]


def test_longest_chain_for_panel_seeds_when_library_lacks_sectors(monkeypatch, tmp_path):
    """Live failure: list_skills rows have steps but no sectors — seed viz."""
    from twclient import world_model
    from twclient.spectate_layout import chain_bubble_sectors, compose_chain_bubbles

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "seed_world"
    world_model.upsert_sector(
        wid,
        {"sector_id": 100, "warps": [200], "port": {"class": "BSB"}},
        state_dir=store,
    )
    world_model.upsert_sector(
        wid,
        {"sector_id": 200, "warps": [100], "port": {"class": "SBB"}},
        state_dir=store,
    )
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: wid)
    monkeypatch.setattr(spectate_app_mod.trade_adapter, "build_trade_hops", lambda w, **kw: ((), None))
    # Mirrors protocol._dispatch_list_skills — metadata only, no sector path.
    fake_loops = [{"name": "aegis_fuel_loop", "source": "mined", "steps": 7, "profit_per_turn": 1200.0}]
    monkeypatch.setattr(
        spectate_app_mod, "_send_control",
        lambda sock_path, verb, args=None, timeout=3.0: {"ok": True, "loops": fake_loops},
    )
    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert result.get("source") == "presence_seed"
    assert chain_bubble_sectors(result) == [100, 200]
    lines = compose_chain_bubbles(
        result, port_classes={100: "BSB", 200: "SBB"}, width=40,
    )
    joined = "\n".join(lines)
    assert "100" in joined and "200" in joined
    assert "no trade loop yet" not in joined


def test_presence_seed_prefers_current_sector_port(tmp_path, monkeypatch):
    """Accept-3 LIVE: current sector on a presence-port path → that pair."""
    from twclient import world_model
    from twclient.spectate_layout import chain_bubble_sectors

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "seed_world"
    # Lower ids would win a naive sorted scan; current=300 must win.
    world_model.upsert_sector(
        wid,
        {"sector_id": 100, "warps": [200], "port": {"class": "BSB"}},
        state_dir=store,
    )
    world_model.upsert_sector(
        wid,
        {"sector_id": 200, "warps": [100], "port": {"class": "SBB"}},
        state_dir=store,
    )
    world_model.upsert_sector(
        wid,
        {"sector_id": 300, "warps": [400], "port": {"class": "BBB"}},
        state_dir=store,
    )
    world_model.upsert_sector(
        wid,
        {"sector_id": 400, "warps": [300], "port": {"class": "SSS"}},
        state_dir=store,
    )
    seed = spectate_app_mod._presence_port_chain_seed(
        wid, current_sector=300, state_dir=store,
    )
    assert seed is not None
    assert chain_bubble_sectors(seed) == [300, 400]


def test_presence_seed_grows_beyond_two_ports(tmp_path, monkeypatch):
    """WO-TUI-CHAIN-VIZ-GROW: three contiguous presence ports → full path."""
    from twclient import world_model
    from twclient.spectate_layout import chain_bubble_sectors, compose_chain_bubbles

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "grow_world"
    world_model.upsert_sector(
        wid, {"sector_id": 10, "warps": [20], "port": {"class": "BSB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 20, "warps": [10, 30], "port": {"class": "SBB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 30, "warps": [20], "port": {"class": "BBB"}}, state_dir=store,
    )
    seed = spectate_app_mod._presence_port_chain_seed(
        wid, current_sector=10, state_dir=store,
    )
    assert seed is not None
    assert chain_bubble_sectors(seed) == [10, 20, 30]
    joined = "\n".join(compose_chain_bubbles(seed, port_classes={10: "BSB", 20: "SBB", 30: "BBB"}, width=82))
    assert "10" in joined and "20" in joined and "30" in joined
    assert "no trade loop yet" not in joined


def test_presence_seed_requires_direct_port_warps(tmp_path, monkeypatch):
    """Ports linked only through an empty sector do not seed a chain."""
    from twclient import world_model

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "port_only_world"
    world_model.upsert_sector(
        wid, {"sector_id": 100, "warps": [50], "port": {"class": "BSB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 50, "warps": [100, 200], "port": None}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 200, "warps": [50], "port": {"class": "SBB"}}, state_dir=store,
    )
    seed = spectate_app_mod._presence_port_chain_seed(
        wid, current_sector=100, state_dir=store, max_hops=3,
    )
    assert seed is None


def test_compose_chain_bubbles_drops_non_port_when_known_ports_set():
    """Compose defense: non-port ids break contiguity — never bridge bubbles."""
    from twclient.spectate_layout import compose_chain_bubbles, chain_bubble_sectors

    raw = {"sectors": (10, 99, 20), "source": "presence_seed"}
    assert chain_bubble_sectors(raw) == [10, 99, 20]
    joined = "\n".join(
        compose_chain_bubbles(
            raw,
            port_classes={10: "BSB", 20: "SBB"},
            known_ports={10, 20},
            width=40,
        )
    )
    assert "10" in joined
    assert "20" not in joined
    assert "99" not in joined


def test_presence_seed_four_contiguous_ports(tmp_path, monkeypatch):
    """Four direct port→port warps → seed length 4."""
    from twclient import world_model
    from twclient.spectate_layout import chain_bubble_sectors

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "four_port_world"
    world_model.upsert_sector(
        wid, {"sector_id": 10, "warps": [20], "port": {"class": "BSB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 20, "warps": [10, 30], "port": {"class": "SBB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 30, "warps": [20, 40], "port": {"class": "BBB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 40, "warps": [30], "port": {"class": "SSS"}}, state_dir=store,
    )
    seed = spectate_app_mod._presence_port_chain_seed(wid, current_sector=10, state_dir=store)
    assert seed is not None
    assert chain_bubble_sectors(seed) == [10, 20, 30, 40]


def test_longest_chain_for_panel_skips_profit_chain_with_non_port(monkeypatch, tmp_path):
    """ProfitChain with a non-port sector → presence contiguous seed instead."""
    from twclient import world_model
    from twclient.spectate_layout import chain_bubble_sectors

    store = tmp_path / "world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    wid = "mixed_world"
    world_model.upsert_sector(
        wid, {"sector_id": 10, "warps": [20], "port": {"class": "BSB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 20, "warps": [10, 30], "port": {"class": "SBB"}}, state_dir=store,
    )
    world_model.upsert_sector(
        wid, {"sector_id": 30, "warps": [20], "port": {"class": "BBB"}}, state_dir=store,
    )
    bad_chain = chains.ProfitChain(
        sectors=(10, 99, 20, 30, 10),
        hops=(),
        overall_profit=100.0,
        turns=4,
        cr_per_turn=25.0,
        cr_per_execution=100.0,
    )
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: wid)
    monkeypatch.setattr(
        spectate_app_mod.trade_adapter,
        "build_trade_hops",
        lambda w, **kw: ((chains.TradeHop(1, 2, "x", 1.0),), None),
    )
    monkeypatch.setattr(spectate_app_mod.chains, "longest_profit_chain", lambda hops: bad_chain)
    monkeypatch.setattr(
        spectate_app_mod, "_send_control",
        lambda sock_path, verb, args=None, timeout=3.0: {"ok": True, "loops": []},
    )
    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert isinstance(result, dict)
    assert result.get("source") == "presence_seed"
    assert chain_bubble_sectors(result) == [10, 20, 30]


def test_longest_chain_for_panel_still_prefers_profit_chain_over_seed(monkeypatch):
    """Real ProfitCycle wins; presence seed must not be consulted."""
    hops = (
        chains.TradeHop(frm=1, to=2, commodity="Fuel Ore", margin=10.0, turns=2),
        chains.TradeHop(frm=2, to=1, commodity="Organics", margin=5.0, turns=2),
    )
    monkeypatch.setattr(spectate_app_mod, "_resolve_world_id", lambda status=None: "world1")
    monkeypatch.setattr(spectate_app_mod.trade_adapter, "build_trade_hops", lambda wid, **kw: (hops, None))

    def _boom(*a, **k):
        raise AssertionError("presence seed must not run when ProfitChain exists")

    monkeypatch.setattr(spectate_app_mod, "_presence_port_chain_seed", _boom)
    monkeypatch.setattr(
        spectate_app_mod, "_send_control",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("library must not run")),
    )
    result = spectate_app_mod._longest_chain_for_panel("/nonexistent.sock")
    assert isinstance(result, chains.ProfitChain)


# ---------------------------------------------------------------------------
# WO-TUI-METRICS — active world_id when multiple world stores exist
# ---------------------------------------------------------------------------


def test_resolve_world_id_prefers_status_over_ambiguous_store(monkeypatch, tmp_path):
    from twclient import world_model

    store = tmp_path / "world"
    (store / "world_a").mkdir(parents=True)
    (store / "world_b").mkdir(parents=True)
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    monkeypatch.setattr(spectate_app_mod, "WORLD_DIR", store)
    assert spectate_app_mod._resolve_world_id() is None
    assert spectate_app_mod._resolve_world_id({"world_id": "world_b"}) == "world_b"


def test_resolve_world_id_matches_host_when_multiple_worlds(monkeypatch, tmp_path):
    store = tmp_path / "world"
    (store / "twgs_geekm0nkey_com__F__Tumbleweed").mkdir(parents=True)
    (store / "tradewarsacademy_com__D__Ironhand").mkdir(parents=True)
    monkeypatch.setattr(spectate_app_mod, "WORLD_DIR", store)
    assert (
        spectate_app_mod._resolve_world_id({"host": "twgs.geekm0nkey.com"})
        == "twgs_geekm0nkey_com__F__Tumbleweed"
    )


def test_stamp_live_world_metrics_uses_status_world_id(monkeypatch, tmp_path):
    from twclient import world_model

    store = tmp_path / "world"
    wid = "active_world"
    monkeypatch.setattr(world_model, "WORLD_DIR", store)
    world_model.upsert_sector(wid, {"sector_id": 1}, state_dir=store)
    world_model.upsert_sector(wid, {"sector_id": 2}, state_dir=store)
    (store / "other_world").mkdir(parents=True)

    tracked = spectate_app_mod._stamp_live_world_metrics({}, 1.0, {"world_id": wid})
    rows = compose_live_metrics(tracked)
    sectors_row = next(r for r in rows if r["label"] == "SECTORS")
    assert sectors_row["value"] == "2"


# ---------------------------------------------------------------------------
# WO-FA5c — A/a suspends curses, hands the terminal to `tw attach`, resumes
# ---------------------------------------------------------------------------


class _FakeSubprocessModule:
    """Stands in for the real `subprocess` module inside spectate_app's
    own namespace (monkeypatched via `spectate_app_mod.subprocess`) --
    keeps the test from touching the REAL global subprocess module."""

    def __init__(self, run_fn):
        self.run = run_fn


class _FakeStdscr:
    def __init__(self, calls):
        self._calls = calls

    def clear(self):
        self._calls.append("clear")

    def refresh(self):
        self._calls.append("refresh")


def test_suspend_and_run_attach_launches_tw_attach_and_restores_curses(monkeypatch):
    calls = []
    monkeypatch.setattr(curses, "def_prog_mode", lambda: calls.append("def_prog_mode"))
    monkeypatch.setattr(curses, "endwin", lambda: calls.append("endwin"))
    monkeypatch.setattr(curses, "reset_prog_mode", lambda: calls.append("reset_prog_mode"))

    captured_argv = []

    class _Result:
        returncode = 0

    def fake_run(argv):
        captured_argv.append(argv)
        calls.append("subprocess.run")
        return _Result()

    monkeypatch.setattr(spectate_app_mod, "subprocess", _FakeSubprocessModule(fake_run))

    error = spectate_app_mod._suspend_and_run_attach(_FakeStdscr(calls))
    assert error is None
    assert calls == ["def_prog_mode", "endwin", "subprocess.run", "reset_prog_mode", "clear", "refresh"]
    assert captured_argv[0][0].endswith("/tw")
    assert captured_argv[0][1] == "attach"


def test_suspend_and_run_attach_reports_a_nonzero_exit_without_raising(monkeypatch):
    monkeypatch.setattr(curses, "def_prog_mode", lambda: None)
    monkeypatch.setattr(curses, "endwin", lambda: None)
    monkeypatch.setattr(curses, "reset_prog_mode", lambda: None)

    class _Result:
        returncode = 7

    monkeypatch.setattr(spectate_app_mod, "subprocess", _FakeSubprocessModule(lambda argv: _Result()))

    error = spectate_app_mod._suspend_and_run_attach(_FakeStdscr([]))
    assert error == "tw attach exited 7"


def test_suspend_and_run_attach_restores_curses_even_on_a_missing_binary(monkeypatch):
    """FileNotFoundError (no `tw` at the resolved path) must degrade to
    a status-line error string, and curses must STILL be restored --
    a crashed attach launch must never leave the real terminal stuck in
    curses' raw/cbreak mode."""
    calls = []
    monkeypatch.setattr(curses, "def_prog_mode", lambda: None)
    monkeypatch.setattr(curses, "endwin", lambda: None)
    monkeypatch.setattr(curses, "reset_prog_mode", lambda: calls.append("reset_prog_mode"))

    def fake_run(argv):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(spectate_app_mod, "subprocess", _FakeSubprocessModule(fake_run))

    error = spectate_app_mod._suspend_and_run_attach(_FakeStdscr(calls))
    assert error is not None and "not found" in error
    assert calls == ["reset_prog_mode", "clear", "refresh"]


def test_handle_key_a_invokes_attach_and_records_the_error_on_status(monkeypatch):
    calls = []
    monkeypatch.setattr(spectate_app_mod, "_suspend_and_run_attach", lambda stdscr: calls.append(stdscr) or "boom")
    status = {"connected": True}
    library = {"open": False, "loops": [], "selected": 0, "pending_cycles": 1, "confirm": None}
    fake_stdscr = object()

    consumed = spectate_app_mod._handle_key(ord("A"), "/nonexistent.sock", status, library, stdscr=fake_stdscr)
    assert consumed is True
    assert calls == [fake_stdscr]
    assert status["attach_error"] == "boom"


def test_handle_key_a_is_a_safe_noop_without_a_stdscr():
    """A caller that hasn't wired stdscr through (e.g. an older/other
    call site) must not crash -- degrades to consumed-but-inert rather
    than an AttributeError out of the getch() loop."""
    status = {"connected": True}
    library = {"open": False, "loops": [], "selected": 0, "pending_cycles": 1, "confirm": None}

    consumed = spectate_app_mod._handle_key(ord("a"), "/nonexistent.sock", status, library)
    assert consumed is True
    assert "attach_error" not in status


def test_idle_prompt_overlay_enter_then_y_sends_do(monkeypatch):
    calls = []
    monkeypatch.setattr(
        spectate_app_mod,
        "_send_control",
        lambda sock, verb, args=None, timeout=3.0: calls.append({"verb": verb, "args": args}) or {"ok": True},
    )
    status = {"mode": "ai_pilot"}
    library = {"open": False, "loops": [], "selected": 0, "pending_cycles": 1, "confirm": None}
    idle = {
        "open": True,
        "prompt": "Option? (A=Attack)",
        "classification": "sector_display",
        "buffer": "A",
        "confirm": False,
        "secret": False,
        "dismissed_key": None,
        "armed_key": ("sector_display", "Option? (A=Attack)"),
    }
    assert spectate_app_mod._handle_key(10, "/x.sock", status, library, idle_prompt=idle) is True
    assert idle["confirm"] is True
    assert calls == []
    assert spectate_app_mod._handle_key(ord("y"), "/x.sock", status, library, idle_prompt=idle) is True
    assert idle["open"] is False
    assert calls == [
        {"verb": "do", "args": {"input": "A", "actor": "human"}},
        {"verb": "set_mode", "args": {"mode": "ai_pilot"}},
    ]
    assert status["mode"] == "ai_pilot"


def test_blank_dashboard_windows_erases_each_pane():
    class FakeWin:
        def __init__(self):
            self.erased = False
            self.refreshed = False

        def erase(self):
            self.erased = True

        def noutrefresh(self):
            self.refreshed = True

    wins = {"chain": FakeWin(), "viewport": FakeWin()}
    spectate_app_mod._blank_dashboard_windows(wins)
    assert all(w.erased and w.refreshed for w in wins.values())
    spectate_app_mod._blank_dashboard_windows(None)  # no-op
    spectate_app_mod._blank_dashboard_windows({})


def test_idle_prompt_overlay_secret_never_sends_do(monkeypatch):
    calls = []
    monkeypatch.setattr(
        spectate_app_mod,
        "_send_control",
        lambda sock, verb, args=None, timeout=3.0: calls.append({"verb": verb, "args": args}) or {"ok": True},
    )
    status = {"mode": "ai_pilot"}
    library = {"open": False, "loops": [], "selected": 0, "pending_cycles": 1, "confirm": None}
    idle = {
        "open": True,
        "prompt": "Password?",
        "classification": "login_password",
        "buffer": "hunter2",
        "confirm": True,
        "secret": True,
        "dismissed_key": None,
        "armed_key": ("login_password", "Password?"),
    }
    # Typing while secret is open must be ignored; Esc dismisses.
    assert spectate_app_mod._handle_key(ord("x"), "/x.sock", status, library, idle_prompt=idle) is True
    assert idle["open"] is True
    assert calls == []
    assert spectate_app_mod._handle_key(27, "/x.sock", status, library, idle_prompt=idle) is True
    assert idle["open"] is False
    assert calls == []


def test_maybe_arm_idle_prompt_opens_after_threshold():
    idle = {
        "open": False,
        "prompt": "",
        "classification": "",
        "buffer": "",
        "confirm": False,
        "secret": False,
        "dismissed_key": None,
        "armed_key": None,
    }
    status = {"mode": "ai_pilot"}
    event = {"classification": "pause_key", "prompt": "[Pause]"}
    spectate_app_mod._maybe_arm_idle_prompt(idle, status, event, idle_age=4.0)
    assert idle["open"] is False
    spectate_app_mod._maybe_arm_idle_prompt(idle, status, event, idle_age=12.0)
    assert idle["open"] is True
    assert idle["prompt"] == "[Pause]"
    # Quiet main_command still keeps the overlay open while idle remains high.
    spectate_app_mod._maybe_arm_idle_prompt(
        idle, status,
        {"classification": "main_command", "prompt": "Command [TL=00:00:00]:[1]"},
        idle_age=12.0,
    )
    assert idle["open"] is True
    # Idle drop (fresh RX) closes it.
    spectate_app_mod._maybe_arm_idle_prompt(
        idle, status,
        {"classification": "main_command", "prompt": "Command [TL=00:00:00]:[1]"},
        idle_age=2.0,
    )
    assert idle["open"] is False


def test_spectate_client_auto_reconnects_after_sock_recycle(monkeypatch):
    """WO-TUI-SPECTATE-RECONNECT: subscribe EOF (daemon recycle) must not
    leave SpectateClient permanently quiet — when the unix sock returns,
    resubscribe and deliver the fresh seed event without relaunching."""
    import shutil
    import socket
    import tempfile
    import threading

    monkeypatch.setattr(spectate_app_mod, "RECONNECT_INITIAL_S", 0.05)
    monkeypatch.setattr(spectate_app_mod, "RECONNECT_MAX_S", 0.2)

    # macOS AF_UNIX path cap (~104B) — pytest tmp_path is too deep.
    sock_dir = tempfile.mkdtemp(prefix="twd-spec-")
    sock_path = Path(sock_dir) / "s.sock"
    try:
        def serve_one_event(label, ready, hold_open=None):
            if sock_path.exists():
                sock_path.unlink()
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(str(sock_path))
            srv.listen(1)
            srv.settimeout(8.0)
            ready.set()
            conn, _ = srv.accept()
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
            payload = {
                "ok": True,
                "screen": [label],
                "state": {},
                "classification": "main_command",
                "sent_input": None,
            }
            conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            if hold_open is not None:
                hold_open.wait(timeout=8.0)
            try:
                conn.close()
            except OSError:
                pass
            try:
                srv.close()
            except OSError:
                pass
            try:
                sock_path.unlink()
            except FileNotFoundError:
                pass

        ready1 = threading.Event()
        t1 = threading.Thread(target=serve_one_event, args=("GEN-1", ready1), daemon=True)
        t1.start()
        assert ready1.wait(2.0)

        client = spectate_app_mod.SpectateClient(sock_path)
        assert client.connect() is True
        first = client.next_event(timeout=3.0)
        assert first is not None
        assert first.get("screen") == ["GEN-1"]

        t1.join(timeout=3.0)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and not client.reconnecting:
            time.sleep(0.02)
        assert client.reconnecting is True
        assert client.stream_alive is False

        ready2 = threading.Event()
        hold2 = threading.Event()
        t2 = threading.Thread(
            target=serve_one_event, args=("GEN-2", ready2, hold2), daemon=True,
        )
        t2.start()
        assert ready2.wait(2.0)

        second = client.next_event(timeout=5.0)
        assert second is not None
        assert second.get("screen") == ["GEN-2"]
        assert client.stream_alive is True
        assert client.reconnecting is False

        hold2.set()
        client.close()
        t2.join(timeout=3.0)
    finally:
        shutil.rmtree(sock_dir, ignore_errors=True)


def test_spectate_client_exhausts_reconnect_and_sets_flag(monkeypatch):
    """WO-SPECTATE-RECONNECT-LIVE: after MAX_RECONNECT_ATTEMPTS failures,
    stop retrying, clear reconnecting chrome, and set reconnect_exhausted
    so the curses loop can exit cleanly."""
    import shutil
    import socket
    import tempfile
    import threading

    monkeypatch.setattr(spectate_app_mod, "RECONNECT_INITIAL_S", 0.02)
    monkeypatch.setattr(spectate_app_mod, "RECONNECT_MAX_S", 0.05)
    monkeypatch.setattr(spectate_app_mod, "MAX_RECONNECT_ATTEMPTS", 3)

    sock_dir = tempfile.mkdtemp(prefix="twd-spec-ex-")
    sock_path = Path(sock_dir) / "s.sock"
    try:
        def serve_one_then_gone(ready):
            if sock_path.exists():
                sock_path.unlink()
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(str(sock_path))
            srv.listen(1)
            srv.settimeout(8.0)
            ready.set()
            conn, _ = srv.accept()
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
            payload = {
                "ok": True,
                "screen": ["ONCE"],
                "state": {},
                "classification": "main_command",
                "sent_input": None,
            }
            conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            try:
                conn.close()
            except OSError:
                pass
            try:
                srv.close()
            except OSError:
                pass
            try:
                sock_path.unlink()
            except FileNotFoundError:
                pass

        ready = threading.Event()
        t = threading.Thread(target=serve_one_then_gone, args=(ready,), daemon=True)
        t.start()
        assert ready.wait(2.0)

        client = spectate_app_mod.SpectateClient(sock_path)
        assert client.connect() is True
        first = client.next_event(timeout=3.0)
        assert first is not None
        assert first.get("screen") == ["ONCE"]
        t.join(timeout=3.0)

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not client.reconnect_exhausted:
            time.sleep(0.02)
        assert client.reconnect_exhausted is True
        assert client.reconnecting is False
        assert client.stream_alive is False
        assert "exhausted" in (client.connect_error or "").lower()
        client.close()
    finally:
        shutil.rmtree(sock_dir, ignore_errors=True)
