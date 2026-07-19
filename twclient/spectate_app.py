"""`tw spectate` — the interactive spectator TUI.

Curses I/O only lives here; the actual dashboard text comes from
spectate_layout.py's pure functions. SpectateClient owns the subscribe
socket + a background reader thread feeding a Queue, so the curses loop
never blocks on the network directly (needed to stay responsive to
resize/Ctrl-C). Fully standalone: this connects to an ALREADY-RUNNING
daemon over its unix socket — it never spawns or drives anything, so it
can run in a separate terminal/process from whatever is playing.

Trainer Control Panel addendum (TUI-POLISH-PLAN.md, 2026-07-19): this
same binary now ALSO sends a small set of META-commands to the daemon's
control plane -- set_mode/play_start/play_stop/play_pause/play_resume,
via short-lived one-shot connections (_send_control(), mirroring
fetch_status()'s existing pattern) -- so it's no longer purely
"read-only" in the literal sense. The distinction that still holds:
NOTHING here ever calls session.send()/send_raw() directly or
indirectly forwards a keystroke to the GAME -- every control verb is a
mode/loop-player transition the operator explicitly triggers, mediated entirely
by the daemon's own control_lock/loop_player. `tw attach` (raw keystroke
pass-through) remains the only thing that actually drives the game
directly.
"""

import curses
import json
import queue
import signal
import socket
import threading
import time

from . import terminal
from .spectate_layout import (
    CLASSIFICATION_PULSE_DURATION_S,
    DEFAULT_EVENT,
    MIN_COLS,
    MIN_LINES,
    TICKER_FLASH_DURATION_S,
    TICKER_MAX,
    compose_control_strip,
    compose_dashboard,
    compose_hud_cells,
    compose_port_panel,
    format_idle_age,
    format_loops_library_header,
    format_loops_library_row,
    format_ticker_entry,
    frame_layout,
    is_recent,
    render_plain,
    status_semantic,
    update_tracked_stats,
)

# MIN_COLS/MIN_LINES are re-exported (not just used internally) --
# twclient/interactive_app.py (the `tw attach` MANUAL-mode viewer, a
# sibling module outside this lane) imports them from here directly, so
# they stay part of this module's public surface even though
# frame_layout() above is now the actual source of truth.

STATUS_POLL_INTERVAL_S = 1.5
# Decoupled animation tick (Phase 0, motion E2): liveness chrome (HUD
# freshness/spinner/heartbeat/status) redraws at this cadence regardless
# of whether a new watch event arrived; the (expensive) viewport redraws
# ONLY on a real event -- that split is the actual CPU/flicker fix, not
# just "redraw less often everywhere".
ANIM_FPS = 13
ANIM_INTERVAL_S = 1.0 / ANIM_FPS
HEARTBEAT_PERIOD_S = 0.8  # slow breathing-dot toggle, distinct from the faster waiting spinner
FLASH_DURATION_S = 0.4    # brief reverse-video pulse on a connect/disconnect transition

# pyte's color names (see twclient/terminal.py's color_map()) -> curses'
# basic-8 constants. pyte calls ANSI code 33 "brown"; every real terminal
# renders it as yellow, so that's what it maps to here. -1 means "use the
# terminal's own default fg/bg" (curses.use_default_colors()).
_PYTE_TO_CURSES_COLOR = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "brown": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
    "default": -1,
}

# curses.KEY_RESIZE (delivered via getch()) covers SIGWINCH on most
# terminals already, but it's not guaranteed everywhere -- an explicit
# handler is cheap insurance. Just sets a flag; the redraw itself happens
# on the main curses thread inside _run()'s loop (curses isn't
# signal-handler-safe to call into directly).
_resize_pending = threading.Event()


def _on_sigwinch(signum, frame):
    _resize_pending.set()


class SpectateClient:
    """Subscribes to the daemon's watch-stream and feeds parsed events
    into a Queue for a consumer (the curses loop, or --snapshot) to read.
    Read-only: never sends anything on the subscribe connection."""

    def __init__(self, sock_path):
        self.sock_path = str(sock_path)
        self.events = queue.Queue()
        self.connect_error = None
        self._sock = None
        self._stop = threading.Event()
        self._thread = None

    def connect(self):
        try:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(self.sock_path)
            self._sock.sendall((json.dumps({"verb": "subscribe", "args": {}}) + "\n").encode("utf-8"))
        except OSError as e:
            self.connect_error = str(e)
            return False
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        return True

    def _reader_loop(self):
        f = self._sock.makefile("rb")
        while not self._stop.is_set():
            try:
                line = f.readline()
            except OSError:
                break
            if not line:
                break
            try:
                event = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            self.events.put(event)

    def next_event(self, timeout=0.1):
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self):
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass


def fetch_status(sock_path, timeout=3.0):
    """One-shot status-verb call on its OWN connection (the subscribe
    connection is dedicated to streaming) — used to populate the status
    line's connected/subscriber-count/idle fields."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(sock_path))
        s.sendall((json.dumps({"verb": "status", "args": {}}) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        s.close()
        resp = json.loads(buf.decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "connected": False,
            "subscriber_count": 0,
            "last_rx_age_s": None,
            "daemon_pid": None,
            "host": None,
            "name": None,
            "mode": "ai_pilot",
            "play": None,
        }
    return {
        "connected": resp.get("connected", False),
        "subscriber_count": resp.get("subscribers", 0),
        "last_rx_age_s": (resp.get("idle_ms", 0) or 0) / 1000.0,
        "daemon_pid": None,  # filled by the caller, which knows the pidfile path
        "host": resp.get("host"),  # header chrome (Phase 1) -- app/host/character/classification
        "name": resp.get("name"),
        # Trainer Control Panel -- control-MODE + AUTO-LOOP live progress
        # (protocol.py's "status" verb, control_lock.py/loop_player.py).
        "mode": resp.get("mode", "ai_pilot"),
        "play": resp.get("play"),
    }


def _send_control(sock_path, verb, args=None, timeout=3.0):
    """One-shot META-command to the daemon's control plane (set_mode/
    play_start/play_stop/play_pause/play_resume) -- same one-shot
    connect/send/read/close shape as fetch_status(), on its OWN
    connection so it never contends with the subscribe stream. Never
    raises: a connect failure or malformed response degrades to a plain
    {"ok": False, "error": ...} the control strip can show, exactly like
    any other rejected verb (e.g. "controller_locked_by_human")."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(str(sock_path))
        s.sendall((json.dumps({"verb": verb, "args": args or {}}) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        s.close()
        return json.loads(buf.decode("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"connect_failed:{e}"}


class _ColorPairs:
    """Lazily allocates curses color pairs for each distinct (fg, bg) cell
    attribute pair actually seen while drawing the MAIN pane, up to
    whatever the terminal supports. `attr_for()` degrades gracefully —
    plain bold/normal, no color pairs — when the terminal has no color
    support at all, or once curses.COLOR_PAIRS is exhausted (both are
    checked, never crash)."""

    def __init__(self):
        self.enabled = False
        self._pair_ids = {}
        self._next_id = 1  # pair 0 is reserved (curses' default pair)
        self._default_bg = -1

    def init(self):
        if not curses.has_colors():
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            self._default_bg = curses.COLOR_BLACK
        self.enabled = True

    def attr_for(self, fg, bg, bold):
        attr = curses.A_BOLD if bold else curses.A_NORMAL
        if not self.enabled:
            return attr
        fg_c = _PYTE_TO_CURSES_COLOR.get(fg, self._default_bg if fg == "default" else curses.COLOR_WHITE)
        bg_c = _PYTE_TO_CURSES_COLOR.get(bg, self._default_bg if bg == "default" else curses.COLOR_BLACK)
        key = (fg_c, bg_c)
        pair_id = self._pair_ids.get(key)
        if pair_id is None:
            if self._next_id >= curses.COLOR_PAIRS:
                pair_id = 0  # exhausted this terminal's color pairs -- fall back to default
            else:
                pair_id = self._next_id
                try:
                    curses.init_pair(pair_id, fg_c, bg_c)
                except curses.error:
                    pair_id = 0
                else:
                    self._next_id += 1
            self._pair_ids[key] = pair_id
        return attr | curses.color_pair(pair_id)


def _draw_pane(win, lines, max_lines, max_cols):
    win.erase()
    for i, line in enumerate(lines[:max_lines]):
        try:
            win.addnstr(i, 0, line, max_cols - 1)
        except curses.error:
            pass  # bottom-right cell write is a known curses quirk — cosmetic only
    win.noutrefresh()


def _draw_ticker(win, lines, max_lines, max_cols, flash_active, palette):
    """Like _draw_pane(), but the NEWEST row (motion B3: newest-ticker-
    row flash-on-arrival) gets a brief highlighted attribute while
    `flash_active` -- an at-a-glance "something just landed" cue on the
    event log, distinct from the HUD's per-field flashes above."""
    win.erase()
    visible = lines[:max_lines]
    flash_attr = palette.attr_for("brown", "default", True)
    last_idx = len(visible) - 1
    for i, line in enumerate(visible):
        attr = flash_attr if (flash_active and i == last_idx) else curses.A_NORMAL
        try:
            win.addnstr(i, 0, line, max_cols - 1, attr)
        except curses.error:
            pass
    win.noutrefresh()


def _draw_main_pane(win, lines, color_rows, max_lines, max_cols, palette):
    """Like _draw_pane(), but paints each color RUN (see
    terminal.color_map()) with its own curses attribute instead of one
    flat style for the whole line. Falls back to a single plain
    addnstr() per row when there's no color data for that row (e.g. the
    daemon hasn't sent a color-aware event yet).

    Kept here (unchanged) for twclient/interactive_app.py -- the `tw
    attach` MANUAL-mode viewer, a sibling module outside this lane --
    which reuses this exact function for its own unbordered pane.
    spectate_app's own bordered viewport uses _draw_viewport() below
    instead, which additionally handles the border + the shared
    _content_inset()."""
    win.erase()
    for i, line in enumerate(lines[:max_lines]):
        runs = color_rows[i] if i < len(color_rows) else None
        if not runs:
            try:
                win.addnstr(i, 0, line, max_cols - 1)
            except curses.error:
                pass
            continue
        for run in runs:
            start = run["start"]
            end = min(run["end"], len(line))
            if start >= end or start >= max_cols - 1:
                continue
            segment = line[start:end]
            attr = palette.attr_for(run["fg"], run["bg"], run["bold"])
            try:
                win.addnstr(i, start, segment, max_cols - 1 - start, attr)
            except curses.error:
                pass
    win.noutrefresh()


_SEMANTIC_COLORS = {
    "ok": ("green", "default", True),
    "warn": ("brown", "default", True),  # pyte's name for ANSI-yellow; see _PYTE_TO_CURSES_COLOR
    "danger": ("red", "default", True),
    "info": ("cyan", "default", False),  # Phase 4: a port's "selling" commodity row
    "gain": ("green", "default", True),  # Phase 3: credit-delta flash, positive
    "loss": ("red", "default", True),    # Phase 3: credit-delta flash, negative
    # Trainer Control Panel's SPECTATE badge (deliberately idle/parked, not
    # a warning -- see _MODE_BADGES in spectate_layout.py). _PYTE_TO_CURSES_COLOR
    # only carries the basic-8 pyte names -- no "brightblack"/grey to reach
    # for -- so "muted" means genuinely uncolored: terminal-default fg/bg,
    # non-bold. The badge itself is still drawn in reverse video
    # (_draw_control_strip), so this reads as a plain, unaccented chip next
    # to the other modes' bold green/yellow/red badges -- exactly the
    # "nothing to see here" register SPECTATE calls for.
    "muted": ("default", "default", False),
}


def _tone_attr(tone, palette, default_attr):
    """The one place every HUD/port-row draw resolves a `tone` (see
    spectate_layout.compose_hud_cells()/compose_port_panel()) into a
    curses attribute -- `None` falls back to whatever the caller's
    normal (non-tinted) attribute would have been. An unrecognized tone
    (a forward-compat mismatch between this build's _SEMANTIC_COLORS and
    a newer producer) degrades the SAME way rather than KeyError-ing the
    whole render loop dead -- a missing color is cosmetic, a crashed
    cockpit is not."""
    if tone is None:
        return default_attr
    spec = _SEMANTIC_COLORS.get(tone)
    if spec is None:
        return default_attr
    return palette.attr_for(*spec)


def _content_inset(region):
    """The ONE shared offset the viewport's border draw AND its
    color-run content draw both key off (Phase 0) -- the load-bearing
    fix so a border can never drift out of alignment with
    terminal.color_map()'s run["start"]/run["end"] indices. Zero inset
    BEYOND the border itself: a border consumes row/col 0 and content
    starts at (1,1); with no border, content starts at (0,0). Never any
    additional padding on the viewport -- see spectate_layout.frame_layout's
    module docstring for why (it would shear the game's own CP437
    box-art, the correctness landmine the plan calls out)."""
    return (1, 1) if region["border"] else (0, 0)


def _draw_box(win, y, x, h, w, tl, tr, bl, br, hchar, vchar, attr):
    """A rectangular border drawn from caller-supplied corner/edge
    glyphs (terminal.glyph_set()'s viewport_* or hud_* keys) -- shared by
    both the (double-line, heavier) viewport border and the (thin,
    rounded) HUD chrome border, so the two weights stay visually
    consistent without duplicating the drawing logic."""
    if h < 2 or w < 2:
        return
    try:
        win.addstr(y, x, tl + hchar * (w - 2) + tr, attr)
    except curses.error:
        pass  # bottom-right cell write is a known curses quirk (see _draw_pane) -- cosmetic only
    for row in range(y + 1, y + h - 1):
        try:
            win.addstr(row, x, vchar, attr)
            win.addstr(row, x + w - 1, vchar, attr)
        except curses.error:
            pass
    try:
        win.addstr(y + h - 1, x, bl + hchar * (w - 2) + br, attr)
    except curses.error:
        pass


def _draw_header(win, text, attr, pulsing=False):
    """`pulsing` (Phase 3 motion B4: classification-change pulse) briefly
    reverses the whole line -- a coarse but unmissable "something just
    changed" signal, cheaper than per-substring attribute splitting for
    a line that's mostly static text anyway."""
    win.erase()
    if pulsing:
        attr |= curses.A_REVERSE
    try:
        win.addnstr(0, 0, text, max(1, win.getmaxyx()[1] - 1), attr)
    except curses.error:
        pass
    win.noutrefresh()


def _draw_header_strip(win, cells, accent_attr, muted_attr, palette):
    """The 82-108 col "minimal" tier's header (Phase 1: "minimal-chrome
    header stat-strip") -- there's no room for a side gutter at this
    width, so the same 5 HUD cells compose_hud_cells() produces get
    packed onto the header line instead of the app/host/classification
    text _draw_header() shows in the wider tiers. Staleness is still
    signaled per-cell via dimming even though there's no room for the
    full "Ns ago" text here -- the gutter tiers show that in full.

    Phase 3 extras ride along cheaply: `tone` recolors a cell (e.g. a
    credit-delta flash) and `chip` appends inline -- both already
    computed by compose_hud_cells(), just narrower staging here than the
    gutter's two-line layout. `spark`/`gauge` are skipped -- no room at
    this width (see module-level scope note where this is called)."""
    win.erase()
    w = win.getmaxyx()[1]
    col = 0
    for i, cell in enumerate(cells):
        if col >= w - 1:
            break
        text = f"{cell['label']} {cell['value']}"
        if cell["chip"]:
            text = f"{text} {cell['chip']}"
        default_attr = muted_attr if cell["stale"] else accent_attr
        attr = _tone_attr(cell["tone"], palette, default_attr)
        try:
            win.addnstr(0, col, text, max(0, w - 1 - col), attr)
        except curses.error:
            pass
        col += len(text)
        if i < len(cells) - 1 and col < w - 1:
            sep = "  ·  "
            try:
                win.addnstr(0, col, sep, max(0, w - 1 - col))
            except curses.error:
                pass
            col += len(sep)
    win.noutrefresh()


def _format_header(event, status):
    """`app · host · character · classification badge` (Phase 1 visual
    E1) -- host/character come off the periodic `status` poll (daemon
    knows the session identity), the badge off the live watch event."""
    host = status.get("host") or "-"
    name = status.get("name") or "-"
    badge = (event.get("classification") or "unknown").replace("_", " ").upper()
    return f"TW SPECTATE · {host} · {name} · {badge}"


def _draw_viewport(win, region, screen_lines, color_rows, glyphs, palette, border_attr):
    """Draws the bordered game viewport. Content is the SAME cropped
    screen/color the daemon already sends (protocol.build_response()'s
    default crop) -- render_cropped()/color_map() in terminal.py
    preserve LEADING blank rows/cols and trim only trailing ones (see
    their docstrings), so row/col 0 of the cropped data IS row/col 0 of
    the true 80x24 grid. Drawing it unmodified at the shared
    _content_inset() origin, into a window fixed at the native 80x24
    (or 82x26 bordered) size, is therefore already "native size,
    centered, not stretched" -- no raw/uncropped fetch needed, and none
    of protocol.py/watch.py/session.py (out of this lane) has to change."""
    win.erase()
    h, w = region["h"], region["w"]
    if region["border"]:
        _draw_box(
            win, 0, 0, h, w,
            glyphs["viewport_tl"], glyphs["viewport_tr"], glyphs["viewport_bl"], glyphs["viewport_br"],
            glyphs["viewport_h"], glyphs["viewport_v"], border_attr,
        )
        try:
            win.addnstr(0, 2, " GAME ", max(0, w - 4), border_attr)
        except curses.error:
            pass
    off_y, off_x = _content_inset(region)
    game_h, game_w = region["game_h"], region["game_w"]
    for i in range(min(game_h, len(screen_lines))):
        line = screen_lines[i]
        runs = color_rows[i] if i < len(color_rows) else None
        row = off_y + i
        if not runs:
            try:
                win.addnstr(row, off_x, line, game_w)
            except curses.error:
                pass
            continue
        for run in runs:
            start = run["start"]
            end = min(run["end"], len(line))
            if start >= end or start >= game_w:
                continue
            segment = line[start:end]
            attr = palette.attr_for(run["fg"], run["bg"], run["bold"])
            try:
                win.addnstr(row, off_x + start, segment, game_w - start, attr)
            except curses.error:
                pass
    win.noutrefresh()


def _draw_hud_gutter(win, region, cells, port_rows, glyphs, palette, muted_attr):
    """The persistent stats HUD (CREDITS/SECTOR/TURNS/CARGO/PROFIT),
    each cell showing its last-known value plus a `freshness` age
    string, dimmed (muted_attr) once stale. Unlike the viewport, this
    pane has no color-run alignment landmine -- it insets 1 col BEYOND
    its own border for legibility, which the viewport must never do.

    Phase 3/4 per-cell extras (spectate_layout.compose_hud_cells()):
    `tone` picks the value's color (gain/loss flash, or a gauge's
    ok/warn/danger); `chip` (CREDITS) appends a floating delta chip
    inline on the value line; `spark`/`gauge` (CREDITS/TURNS
    respectively) append inline on the freshness line -- kept off the
    value line so the label+value pair stays a stable, easy-to-scan
    column across all 5 cells.

    `port_rows` (compose_port_panel()) render as extra lines AFTER the
    5 stat cells, only while a port is actually the current screen --
    the gutter has plenty of spare height in the tiers that show it."""
    win.erase()
    h, w = region["h"], region["w"]
    accent_attr = palette.attr_for("cyan", "default", False)
    _draw_box(
        win, 0, 0, h, w,
        glyphs["hud_tl"], glyphs["hud_tr"], glyphs["hud_bl"], glyphs["hud_br"],
        glyphs["hud_h"], glyphs["hud_v"], accent_attr,
    )
    try:
        win.addnstr(0, 2, " HUD ", max(0, w - 4), accent_attr)
    except curses.error:
        pass
    col = 2  # 1 for the border + 1 extra breathing-room inset (see docstring)
    row = 2
    for cell in cells:
        if row >= h - 1:
            break
        value_attr = _tone_attr(cell["tone"], palette, muted_attr if cell["stale"] else curses.A_NORMAL)
        value_text = cell["value"]
        if cell["chip"]:
            value_text = f"{value_text}  {cell['chip']}"
        try:
            win.addnstr(row, col, f"{cell['label']:<8}", max(0, w - col - 1), curses.A_BOLD)
            win.addnstr(row, col + 8, value_text, max(0, w - col - 9), value_attr)
        except curses.error:
            pass
        if row + 1 < h - 1:
            extra = cell["freshness"]
            suffix = cell.get("spark") or cell.get("gauge") or ""
            if suffix:
                extra = f"{extra}  {suffix}" if extra else suffix
            if extra:
                try:
                    win.addnstr(row + 1, col, extra, max(0, w - col - 1), value_attr)
                except curses.error:
                    pass
        row += 3  # 2 content lines + 1 blank spacer between cells

    if port_rows and row < h - 1:
        try:
            win.addnstr(row, col, "PORT", max(0, w - col - 1), curses.A_BOLD)
        except curses.error:
            pass
        row += 1
        for prow in port_rows:
            if row >= h - 1:
                break
            tone_attr = _tone_attr(prow["tone"], palette, curses.A_NORMAL)
            text = f"{prow['name']:<10}{prow['bar']} {prow['pct']:>3}%"
            try:
                win.addnstr(row, col, text, max(0, w - col - 1), tone_attr)
            except curses.error:
                pass
            row += 1
    win.noutrefresh()


def _draw_status(win, region, connected, semantic, spinner_char, heartbeat_char, idle_text, flash_active, palette):
    """Liveness bar (Phase 2): breathing heartbeat + waiting spinner +
    locally-ticked idle-age, semantically colored (green/amber/red), a
    brief reverse-video flash on a connect/disconnect transition."""
    win.erase()
    w = region["w"]
    # status_semantic() only ever returns ok/warn/danger today, but this
    # mirrors _tone_attr()'s defensive .get() rather than a second
    # unguarded subscript -- same class of bug, same fix (see _tone_attr).
    fg, bg, bold = _SEMANTIC_COLORS.get(semantic, _SEMANTIC_COLORS["ok"])
    attr = palette.attr_for(fg, bg, bold)
    if flash_active:
        attr |= curses.A_REVERSE
    conn_word = "CONNECTED" if connected else "DISCONNECTED"
    left = f"{heartbeat_char} {conn_word}  {spinner_char} idle {idle_text}"
    right = "q quit"
    try:
        win.addnstr(0, 0, left, max(0, w - 1), attr)
    except curses.error:
        pass
    rx = max(0, w - len(right) - 1)
    try:
        win.addnstr(0, rx, right, max(0, w - 1 - rx))
    except curses.error:
        pass
    win.noutrefresh()


def _draw_control_strip(win, region, strip, palette):
    """Trainer Control Panel's control strip (TUI-POLISH-PLAN.md): MODE
    badge (color-coded, reverse-video so it reads as a badge rather than
    plain text) + live TX ("→ 158") + either a live AUTO-LOOP
    cycle-progress bar or the keybinding hint legend on the right --
    `strip` is spectate_layout.compose_control_strip()'s pre-composed
    dict, this function only lays it out and colors the badge."""
    win.erase()
    w = region["w"]
    accent_attr = palette.attr_for("cyan", "default", False)
    badge_attr = curses.A_REVERSE
    if strip["badge_tone"] is not None:
        badge_attr |= _tone_attr(strip["badge_tone"], palette, curses.A_NORMAL)
    col = 0
    try:
        win.addnstr(0, col, strip["badge"], max(0, w - 1 - col), badge_attr)
    except curses.error:
        pass
    col += len(strip["badge"]) + 1

    tx_text = strip["tx"]
    try:
        win.addnstr(0, col, tx_text, max(0, w - 1 - col), curses.A_NORMAL)
    except curses.error:
        pass

    right_text = strip["right"]
    rx = max(col, w - len(right_text) - 1)
    try:
        win.addnstr(0, rx, right_text, max(0, w - 1 - rx), accent_attr)
    except curses.error:
        pass
    win.noutrefresh()


def _draw_loops_library(stdscr, lines, cols, loops, selected, pending_cycles, confirm, palette):
    """The Learned-Loops Library overlay (`L`) -- a full-screen modal
    listing every saved skill, drawn directly on stdscr (not a
    persistent pane like the dashboard's regions: it appears/disappears
    entirely on a keypress, so there's no reflow-tier geometry to cache
    between frames) while `library_open` is true, REPLACING the normal
    dashboard for as long as it's open. Esc/L (handled by the caller)
    closes it without side effects; Enter no longer starts the loop
    directly -- it ARMS a y/N confirm gate (see _handle_key) since this
    fires a live-money action (play_start), and a passive-looking panel
    must never one-keystroke-launch one (the operator lost ~9k credits to exactly
    that). `confirm` is the chosen loop dict while that gate is up
    (replaces the "cycles armed" line with the confirm prompt), else
    None for the normal list."""
    stdscr.erase()
    accent_attr = palette.attr_for("cyan", "default", False)
    header = format_loops_library_header(len(loops))
    try:
        stdscr.addnstr(0, 0, header, max(1, cols - 1), curses.A_BOLD)
    except curses.error:
        pass
    if confirm is not None:
        prompt = f'Play "{confirm["name"]}" x{pending_cycles} LIVE? y/N'
        # "danger" tone (the SAME red/bold vocabulary status/gauge cells
        # use for a real hazard, not a cosmetic accent) + reverse-video so
        # this reads as unmissable, not just another list row.
        confirm_attr = _tone_attr("danger", palette, curses.A_BOLD) | curses.A_REVERSE
        try:
            stdscr.addnstr(1, 0, prompt, max(1, cols - 1), confirm_attr)
        except curses.error:
            pass
    else:
        try:
            stdscr.addnstr(1, 0, f"cycles armed: {pending_cycles}", max(1, cols - 1), accent_attr)
        except curses.error:
            pass
    if not loops:
        try:
            stdscr.addnstr(3, 0, "(no learned loops yet -- `tw record`/`tw mine` first)", max(1, cols - 1))
        except curses.error:
            pass
    else:
        for i, loop in enumerate(loops):
            row = 3 + i
            if row >= lines - 1:
                break
            is_selected = i == selected
            row_text = format_loops_library_row(loop, is_selected, cols)
            attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
            try:
                stdscr.addnstr(row, 0, row_text, max(1, cols - 1), attr)
            except curses.error:
                pass
    stdscr.noutrefresh()
    curses.doupdate()


def _build_windows(regions):
    """Persistent per-pane windows (Phase 0, motion E1) -- built ONCE
    per distinct `regions` shape (i.e. only on resize/reflow-tier
    change), not every frame. A pathological terminal size that makes
    curses.newwin() itself fail just drops that one pane rather than
    crashing the whole loop."""
    windows = {}
    for key in ("header", "viewport", "gutter", "ticker", "control", "status"):
        r = regions.get(key)
        if r is None:
            continue
        h, w = max(1, r["h"]), max(1, r["w"])
        try:
            windows[key] = curses.newwin(h, w, r["y"], r["x"])
        except curses.error:
            continue
    return windows


def _handle_key(ch, sock_path, status, library):
    """Trainer Control Panel keybindings -- mutates `library` (dict:
    open/loops/selected/pending_cycles/confirm) in place and fires at
    most one _send_control() META-command per keypress. Kept as its own function
    (not inlined in _run()'s already-large loop) so the library-open
    sub-mode's key handling doesn't tangle with the normal dashboard's.
    Returns True if this key was consumed as a Trainer Control Panel
    command (caller should NOT also treat it as detach/resize)."""
    if library["open"]:
        if library.get("confirm") is not None:
            # y/N confirm gate (Enter alone must NEVER fire play_start --
            # it's a live-money action, see _draw_loops_library's
            # docstring). ch == -1 is "no key this tick" (nodelay/timeout
            # polling), not a real keypress -- must NOT count as a cancel,
            # or the prompt would self-cancel on the very next idle frame
            # before the operator could ever answer it. Any REAL key other than
            # y/Y -- Esc, n/N, arrows, whatever -- cancels back to the
            # list with NO send: default is SAFE.
            if ch in (ord("y"), ord("Y")):
                chosen = library["confirm"]
                _send_control(sock_path, "play_start", {"name": chosen["name"], "cycles": library["pending_cycles"]})
                library["confirm"] = None
                library["open"] = False
            elif ch != -1:
                library["confirm"] = None
            return True
        if ch in (27, ord("l"), ord("L")):  # Esc or L closes, no side effects
            library["open"] = False
        elif ch in (curses.KEY_UP, ord("k")) and library["loops"]:
            library["selected"] = (library["selected"] - 1) % len(library["loops"])
        elif ch in (curses.KEY_DOWN, ord("j")) and library["loops"]:
            library["selected"] = (library["selected"] + 1) % len(library["loops"])
        elif ord("1") <= ch <= ord("9"):
            library["pending_cycles"] = ch - ord("0")
        elif ch in (10, 13, curses.KEY_ENTER) and library["loops"]:
            # ARM the confirm gate -- does NOT send play_start itself
            # (see the confirm branch above, handled on the NEXT keypress).
            library["confirm"] = library["loops"][library["selected"]]
        return True

    if ch in (ord("l"), ord("L")):
        resp = _send_control(sock_path, "list_skills")
        library["loops"] = resp.get("loops", []) if resp.get("ok") else []
        library["selected"] = 0
        library["pending_cycles"] = 1
        library["confirm"] = None  # a fresh open must never inherit a stale confirm
        library["open"] = True
        return True
    if ch in (ord("m"), ord("M")):
        # Only ai_pilot<->spectate is reachable from HERE -- MODE_HUMAN is
        # only enterable via a separate `tw attach` process's own
        # connection, MODE_AUTO_LOOP only via play_start (Library/Enter)
        # -- see control_lock.py's module docstring for why each
        # exclusive mode has its own dedicated door, never a generic cycle.
        next_mode = "spectate" if status.get("mode") == "ai_pilot" else "ai_pilot"
        _send_control(sock_path, "set_mode", {"mode": next_mode})
        return True
    if ch in (ord("x"), ord("X")):
        _send_control(sock_path, "play_stop")
        return True
    if ch == ord(" "):
        play = status.get("play") or {}
        if play.get("running"):
            _send_control(sock_path, "play_resume" if play.get("paused") else "play_pause")
        return True
    if ch in (ord("p"), ord("P")):
        # Panic (plan: "halt ALL automation -> SPECTATE") -- ALWAYS both
        # calls, regardless of what's currently running: play_stop() is
        # a harmless no-op if nothing's playing, and set_mode(spectate)
        # explicitly parks in the paused state rather than just falling
        # back to ai_pilot the way a plain play_stop alone would.
        _send_control(sock_path, "play_stop")
        _send_control(sock_path, "set_mode", {"mode": "spectate"})
        return True
    return False


def _run(stdscr, client, sock_path, pid_path, unicode_ok):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(50)
    prev_handler = signal.signal(signal.SIGWINCH, _on_sigwinch)
    _resize_pending.clear()
    palette = _ColorPairs()
    palette.init()
    glyphs = terminal.glyph_set(unicode_ok)

    ticker_history = []
    last_event = dict(DEFAULT_EVENT)
    tracked = {}
    status = {
        "connected": False, "subscriber_count": 0, "last_rx_age_s": None,
        "daemon_pid": None, "host": None, "name": None,
        "mode": "ai_pilot", "play": None,
    }
    last_status_poll = 0.0
    status_poll_ts = 0.0
    prev_connected = None
    flash_until = 0.0
    library = {"open": False, "loops": [], "selected": 0, "pending_cycles": 1, "confirm": None}

    windows = {}
    regions = None
    last_anim = 0.0
    anim_tick = 0

    try:
        while True:
            ch = stdscr.getch()
            if ch == 3:  # Ctrl-C -- ALWAYS detaches immediately, even mid-overlay
                return  # (never let the library submode trap the user with no way out)
            library_was_open = library["open"]
            if _handle_key(ch, sock_path, status, library):
                pass  # Trainer Control Panel consumed it -- fall through to redraw
            elif ch in (ord("q"), ord("Q")):  # detach, don't touch the daemon
                return
            if ch == curses.KEY_RESIZE or _resize_pending.is_set():
                curses.update_lines_cols()
                _resize_pending.clear()

            got_content = False
            if library_was_open and not library["open"]:
                # The overlay draws straight onto stdscr, covering rows/
                # cols the dashboard's persistent sub-windows (Phase 0)
                # don't ALL redraw on a quiet frame (got_content-gated,
                # e.g. the viewport) -- without a full erase here, closing
                # it leaves stale overlay text behind on the real
                # terminal until the next real content redraw happens to
                # touch every pane. Force one now, mirroring the existing
                # "windows just rebuilt" full-redraw path below.
                stdscr.erase()
                stdscr.noutrefresh()
                got_content = True

            event = client.next_event(timeout=0.03)
            if event is not None:
                last_event = event
                ticker_history.append(event)
                tracked = update_tracked_stats(tracked, event, time.monotonic())
                got_content = True

            now = time.monotonic()
            if now - last_status_poll > STATUS_POLL_INTERVAL_S:
                new_status = fetch_status(sock_path)
                new_status["daemon_pid"] = pid_path.read_text().strip() if pid_path.exists() else None
                if prev_connected is not None and new_status["connected"] != prev_connected:
                    flash_until = now + FLASH_DURATION_S  # connection/settle transition flash
                prev_connected = new_status["connected"]
                status = new_status
                status_poll_ts = now
                last_status_poll = now
                got_content = True

            anim_due = (now - last_anim) >= ANIM_INTERVAL_S
            if anim_due:
                anim_tick += 1
                last_anim = now

            lines, cols = stdscr.getmaxyx()
            new_regions = frame_layout(lines, cols)
            if new_regions != regions:
                windows = _build_windows(new_regions)
                regions = new_regions
                got_content = True  # freshly (re)built windows need a full content redraw
                stdscr.erase()
                stdscr.noutrefresh()

            if regions["mode"] == "too_small":
                stdscr.erase()
                try:
                    stdscr.addnstr(0, 0, regions["message"], max(1, cols - 1))
                except curses.error:
                    pass
                stdscr.refresh()
                continue

            if library["open"]:
                # The overlay REPLACES the normal dashboard entirely --
                # background polling above still keeps `status`/events
                # fresh so the moment it closes, the dashboard resumes
                # with current data, not a stale snapshot.
                _draw_loops_library(
                    stdscr, lines, cols, library["loops"], library["selected"], library["pending_cycles"],
                    library.get("confirm"), palette,
                )
                continue

            if not (got_content or anim_due):
                continue  # the idle-CPU win (Phase 0): nothing changed, nothing animating

            idle_age = None
            if status.get("last_rx_age_s") is not None:
                idle_age = status["last_rx_age_s"] + (now - status_poll_ts)
            semantic = status_semantic(status.get("connected", False), idle_age)

            _render(
                windows, regions, last_event, tracked, ticker_history, status,
                palette, glyphs, now, anim_tick, idle_age, semantic,
                flash_active=(now < flash_until), got_content=got_content,
            )
    finally:
        signal.signal(signal.SIGWINCH, prev_handler)


def _render(windows, regions, event, tracked, ticker_history, status, palette, glyphs, now, anim_tick, idle_age, semantic, flash_active, got_content):
    connected = status.get("connected", False)
    accent_attr = palette.attr_for("cyan", "default", True)
    muted_attr = curses.A_DIM if hasattr(curses, "A_DIM") else curses.A_NORMAL

    def _cells():
        # Single call site for compose_hud_cells() with the actual
        # capability-correct glyphs -- both header-strip and gutter draw
        # from the SAME cell list each render, so tone/chip/spark/gauge
        # never disagree between the two.
        return compose_hud_cells(
            tracked, now, mark=glyphs["freshness_mark"],
            delta_up=glyphs["delta_up"], delta_down=glyphs["delta_down"],
            bar_full=glyphs["bar_full"], bar_empty=glyphs["bar_empty"],
        )

    # Phase 3 transient-animation windows -- all sourced off timestamps
    # update_tracked_stats() already recorded, so the fade-out itself
    # needs no loop-level state, just "is `now` still inside the window".
    classification_pulsing = is_recent(tracked.get("_classification_pulse_ts"), now, CLASSIFICATION_PULSE_DURATION_S)
    ticker_flashing = is_recent(tracked.get("_ticker_flash_ts"), now, TICKER_FLASH_DURATION_S)

    # The header is either a classification banner (event-driven, like
    # the viewport below) or, in the "minimal" tier with no side gutter,
    # the HUD stat-strip -- both need the same every-tick redraw as the
    # gutter (freshness ticking, and now the classification pulse fading
    # out over CLASSIFICATION_PULSE_DURATION_S with no new event).
    if regions["header"] is not None and "header" in windows:
        if regions["mode"] == "minimal":
            _draw_header_strip(windows["header"], _cells(), accent_attr, muted_attr, palette)
        elif got_content or classification_pulsing:
            _draw_header(windows["header"], _format_header(event, status), accent_attr, pulsing=classification_pulsing)

    # The viewport only changes when a new event actually arrived (or
    # the panes were just rebuilt) -- the expensive draw stays
    # event-driven, not tied to the animation tick.
    if got_content:
        if regions["viewport"] is not None and "viewport" in windows:
            border_attr = accent_attr if connected else palette.attr_for("red", "default", False)
            _draw_viewport(
                windows["viewport"], regions["viewport"],
                event.get("screen") or [], event.get("color") or [],
                glyphs, palette, border_attr,
            )

    # The ticker redraws on a new event OR while its newest-row flash
    # (motion B3) is still fading -- unlike the viewport, it needs a
    # couple of tick-driven redraws after the event that triggered it.
    if regions["ticker"] is not None and "ticker" in windows and (got_content or ticker_flashing):
        lines = [format_ticker_entry(e) for e in ticker_history[-TICKER_MAX:]]
        _draw_ticker(windows["ticker"], lines, regions["ticker"]["h"], regions["ticker"]["w"], ticker_flashing, palette)

    # The HUD gutter and status bar redraw every call (they're both
    # small/cheap) since freshness/spinner/heartbeat/idle-age (and now
    # the tween/flash/sparkline/gauge) all tick locally between events.
    if regions["gutter"] is not None and "gutter" in windows:
        port_rows = compose_port_panel(event, bar_full=glyphs["bar_full"], bar_empty=glyphs["bar_empty"])
        _draw_hud_gutter(windows["gutter"], regions["gutter"], _cells(), port_rows, glyphs, palette, muted_attr)

    # Trainer Control Panel's control strip -- redraws every call (cheap,
    # same reasoning as the gutter/status above): the live AUTO-LOOP
    # progress bar ticks with every status poll even between real events.
    if regions["control"] is not None and "control" in windows:
        strip = compose_control_strip(status.get("mode", "ai_pilot"), event.get("sent_input"), status.get("play"))
        _draw_control_strip(windows["control"], regions["control"], strip, palette)

    if "status" in windows:
        spinner_char = glyphs["spinner"][anim_tick % len(glyphs["spinner"])]
        heartbeat_char = glyphs["heartbeat"][int(now / HEARTBEAT_PERIOD_S) % len(glyphs["heartbeat"])]
        idle_text = format_idle_age(idle_age) if idle_age is not None else "-"
        _draw_status(
            windows["status"], regions["status"], connected, semantic,
            spinner_char, heartbeat_char, idle_text, flash_active, palette,
        )

    curses.doupdate()


def run_interactive(sock_path, pid_path):
    """Entry point for the real curses TUI. Not a TTY / too small is
    handled inside the loop (message, no crash); Ctrl-C detaches
    cleanly without touching the daemon."""
    client = SpectateClient(sock_path)
    if not client.connect():
        print(f"ERROR: could not connect to daemon at {sock_path}: {client.connect_error}")
        print("Is the daemon running? (`tw status`)")
        return 1
    # Must happen BEFORE curses.wrapper()/initscr() -- see
    # terminal.init_locale()'s docstring.
    unicode_ok = terminal.init_locale()
    try:
        curses.wrapper(_run, client, sock_path, pid_path, unicode_ok)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
    return 0


def run_snapshot(sock_path, pid_path, frames=1, settle_wait_s=8.0):
    """Non-interactive path: connect, print `frames` dashboard(s) as
    plain text to stdout as they arrive. No curses — this is what's
    capturable in a Bash transcript. subscribe() always seeds an
    immediate event on connect, so frame 1 is near-instant; later frames
    wait up to settle_wait_s each for the next real settle-edge and stop
    early (fewer than `frames` printed) if the game goes quiet."""
    client = SpectateClient(sock_path)
    if not client.connect():
        print(f"ERROR: could not connect to daemon at {sock_path}: {client.connect_error}")
        return 1

    ticker_history = []
    last_event = dict(DEFAULT_EVENT)
    printed = 0
    try:
        while printed < frames:
            event = client.next_event(timeout=settle_wait_s)
            if event is None:
                break  # nothing new within the wait window -- stop here
            last_event = event
            ticker_history.append(event)
            status = fetch_status(sock_path)
            status["daemon_pid"] = pid_path.read_text().strip() if pid_path.exists() else None
            dashboard = compose_dashboard(last_event, ticker_history, status)
            print(render_plain(dashboard))
            print()
            printed += 1
    finally:
        client.close()
    return 0
