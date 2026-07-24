"""pyte-backed 80x25 terminal emulator + token-efficient cropped rendering."""

import locale

import pyte


class TerminalScreen:
    def __init__(self, columns=80, lines=25):
        self.columns = columns
        self.lines = lines
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream(self.screen)

    def feed(self, data: bytes):
        """Feed IAC-stripped bytes into the emulator.

        TWGS is a DOS BBS door: its box-drawing/line-art bytes (0xB0-0xDF
        etc.) are CP437, not UTF-8 — decoding as UTF-8 (pyte.ByteStream's
        default) renders them as mojibake. CP437 is single-byte (every
        byte maps to exactly one code point), so decoding per-chunk is
        safe even when a chunk boundary falls mid-glyph-run — there's no
        multi-byte sequence to split. ANSI/VT escape bytes are all <0x80
        and decode identically under cp437 and ASCII, so this only
        changes the high-byte art glyphs, not control sequences.
        """
        if data:
            self.stream.feed(data.decode("cp437"))

    def raw_display(self):
        """The full, uncropped 80x25 grid as a list of row strings."""
        return list(self.screen.display)

    def _cropped_bounds(self):
        """(max_row, max_col) of the content bounding box, or (-1, -1) if
        the screen is entirely blank. Shared by render_cropped() and
        color_map() so both always describe the exact same box -- callers
        zip text rows with color runs by index, and that alignment has to
        hold or a spectator would color the wrong cells."""
        rows = self.raw_display()
        max_row = -1
        max_col = -1
        for i, row in enumerate(rows):
            content_len = len(row.rstrip())
            if content_len > 0:
                max_row = i
                if content_len - 1 > max_col:
                    max_col = content_len - 1
        return max_row, max_col

    def render_cropped(self):
        """The grid cropped to its content bounding box.

        Trailing blank rows (bottom) and trailing blank columns (right)
        are trimmed; leading blank rows/columns are preserved since they
        can be meaningful layout. This is the default, token-efficient
        view handed to the agent.
        """
        max_row, max_col = self._cropped_bounds()
        if max_row == -1:
            return []
        rows = self.raw_display()
        return [rows[i][: max_col + 1] for i in range(max_row + 1)]

    def color_map(self):
        """Per-cell color/bold attributes, run-length-encoded per row for
        compactness, over the SAME bounding box as render_cropped(). Each
        row is a list of runs: {"start": c0, "end": c1 (exclusive), "fg":
        name, "bg": name, "bold": bool} — fg/bg are pyte's color names
        ("red", "green", "brown", "blue", "magenta", "cyan", "white",
        "black", "default"). Sourced from pyte.Screen.buffer, which
        carries the SGR attributes the server actually sent (not just the
        plain text .display does).
        """
        max_row, max_col = self._cropped_bounds()
        if max_row == -1:
            return []
        buffer = self.screen.buffer
        color_rows = []
        for r in range(max_row + 1):
            row_buf = buffer[r]
            runs = []
            current = None
            for c in range(max_col + 1):
                cell = row_buf[c]
                if current is not None and (
                    current["fg"] == cell.fg and current["bg"] == cell.bg and current["bold"] == cell.bold
                ):
                    current["end"] = c + 1
                else:
                    current = {"start": c, "end": c + 1, "fg": cell.fg, "bg": cell.bg, "bold": cell.bold}
                    runs.append(current)
            color_rows.append(runs)
        return color_rows

    def cursor(self):
        c = self.screen.cursor
        return {"x": c.x, "y": c.y}


def init_locale():
    """Call once at startup, BEFORE curses.wrapper() -- ncurses needs the
    process locale set to render wide/non-ASCII glyphs correctly, and
    that has to happen before initscr(). Returns True when the resulting
    locale's preferred encoding is UTF-8 (safe to draw the Unicode
    chrome glyphs in glyph_set() below), False otherwise -- callers fall
    back to the plain-ASCII glyph set in that case. This is a one-time
    capability probe for OUR OWN chrome output, distinct from the CP437
    decode above (TerminalScreen.feed), which is about correctly reading
    the DOS door's game-art bytes regardless of local terminal locale."""
    locale.setlocale(locale.LC_ALL, "")
    encoding = locale.getpreferredencoding().lower()
    return "utf-8" in encoding or "utf8" in encoding


# Two parallel glyph tables so every chrome element (viewport border, HUD
# chrome, liveness spinner/heartbeat, freshness/delta marks) degrades
# together under a single unicode_ok flag from init_locale() -- never a
# per-glyph guess. Weight hierarchy: double-line on the game VIEWPORT
# (heavier border = focus, BBS/DOS-door echo), thin rounded line on HUD
# chrome.
GLYPHS_UNICODE = {
    "viewport_tl": "╔", "viewport_tr": "╗",
    "viewport_bl": "╚", "viewport_br": "╝",
    "viewport_h": "═", "viewport_v": "║",
    "hud_tl": "╭", "hud_tr": "╮",
    "hud_bl": "╰", "hud_br": "╯",
    "hud_h": "─", "hud_v": "│",
    "spinner": ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"),
    "heartbeat": ("●", "○"),  # filled / hollow -- a slow breathing pulse
    "freshness_mark": "✦",
    "delta_up": "▲",
    "delta_down": "▼",
    "bar_full": "█",   # %-meters, turns-left fuel gauge
    "bar_empty": "░",
    "sparkline": "▁▂▃▄▅▆▇█",  # credits sparkline ramp, low->high
}
GLYPHS_ASCII = {
    "viewport_tl": "+", "viewport_tr": "+",
    "viewport_bl": "+", "viewport_br": "+",
    "viewport_h": "=", "viewport_v": "|",
    "hud_tl": "+", "hud_tr": "+",
    "hud_bl": "+", "hud_br": "+",
    "hud_h": "-", "hud_v": "|",
    "spinner": ("|", "/", "-", "\\"),
    "heartbeat": ("*", "."),
    "freshness_mark": "*",
    "delta_up": "^",
    "delta_down": "v",
    "bar_full": "#",   # ASCII meter fallback "[###..]"
    "bar_empty": ".",
    "sparkline": ".-=#",
}


def glyph_set(unicode_ok: bool) -> dict:
    """Select the chrome glyph table -- the single switch every drawing
    helper keys off, so a non-UTF-8 terminal degrades consistently
    rather than per-element (mirrors this module's existing CP437-vs-
    mojibake discipline for game art, one level up at the chrome layer)."""
    return GLYPHS_UNICODE if unicode_ok else GLYPHS_ASCII
