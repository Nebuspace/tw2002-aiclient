"""Pre-cockpit launcher + create-profile form (WO-P1-010…012).

Credentials/secrets are never collected or shown on these surfaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

import curses

from tw2002_aiclient.cockpit import draw as cockpit_draw
from tw2002_aiclient.cockpit.layout import frame_layout
from tw2002_aiclient.cockpit.strip import compose_profile_strip_from_row
from tw2002_aiclient.session import credentials


@dataclass(frozen=True)
class ProfileRow:
    """Non-secret profile summary for the picker (world-identity columns)."""

    name: str
    handle: str
    server: str  # catalog key or bare host label
    game_letter: str = ""
    host: str = ""  # resolved host for world-identity display
    autopilot: bool = False  # capability flag shown (ok tint) — not an armed run
    error: str | None = None  # parse failure — row stays visible (never dropped)


TITLE = " TW2002 AICLIENT "
SUBTITLE = " SELECT PROFILE "
CREATE_CTA = "Create New Player"
CREATE_TITLE = " CREATE NEW PLAYER "

# Shared 7-tone table (visual-language / archived spectate_app._SEMANTIC_COLORS).
# Values: (curses_fg_name, bold). "muted" = terminal default, non-bold.
_SEMANTIC_COLORS: dict[str, tuple[str, bool]] = {
    "ok": ("green", True),
    "warn": ("yellow", True),
    "danger": ("red", True),
    "info": ("cyan", False),  # chrome only — never row data
    "gain": ("green", True),
    "loss": ("red", True),
    "muted": ("default", False),
}

_COLOR_NAME_TO_CURSES = {
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "red": curses.COLOR_RED,
    "cyan": curses.COLOR_CYAN,
    "default": -1,
}

# Thin-rounded HUD chrome (launcher has no live viewport — never double-line).
_GLYPHS_UNICODE = {
    "tl": "╭",
    "tr": "╮",
    "bl": "╰",
    "br": "╯",
    "h": "─",
    "v": "│",
    "sel": "▸",
}
_GLYPHS_ASCII = {
    "tl": "+",
    "tr": "+",
    "bl": "+",
    "br": "+",
    "h": "-",
    "v": "|",
    "sel": ">",
}


def _unicode_ok() -> bool:
    """ASCII force via ``TW2002_ASCII=1``; otherwise prefer UTF-8-capable locale."""
    import os

    if os.environ.get("TW2002_ASCII", "").strip() == "1":
        return False
    return True


def _glyph_set() -> dict[str, str]:
    return _GLYPHS_UNICODE if _unicode_ok() else _GLYPHS_ASCII


def _safe_addstr(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        max_y, max_x = win.getmaxyx()
        if y < 0 or y >= max_y or x >= max_x:
            return
        clipped = text[: max(0, max_x - x - 1)]
        if clipped:
            win.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def _draw_chrome_box(win: curses.window, attr: int) -> None:
    """Thin-rounded (or ASCII twin) chrome box — cyan is chrome, never data."""
    glyphs = _glyph_set()
    try:
        max_y, max_x = win.getmaxyx()
    except curses.error:
        return
    if max_y < 2 or max_x < 2:
        return
    h, v = glyphs["h"], glyphs["v"]
    _safe_addstr(win, 0, 0, glyphs["tl"] + h * (max_x - 2) + glyphs["tr"], attr)
    for y in range(1, max_y - 1):
        _safe_addstr(win, y, 0, v, attr)
        _safe_addstr(win, y, max_x - 1, v, attr)
    _safe_addstr(win, max_y - 1, 0, glyphs["bl"] + h * (max_x - 2) + glyphs["br"], attr)


class _TonePalette:
    """Resolve `_SEMANTIC_COLORS` tones to curses attrs (one table for the launcher)."""

    def __init__(self) -> None:
        self._attrs: dict[str, int] = {}
        self._init()

    def _init(self) -> None:
        if not curses.has_colors():
            # Monochrome: bold ≈ attention; underline ≈ warn; reverse still selection.
            self._attrs = {
                "ok": curses.A_BOLD,
                "warn": curses.A_BOLD | curses.A_UNDERLINE,
                "danger": curses.A_BOLD,
                "info": curses.A_BOLD,
                "gain": curses.A_BOLD,
                "loss": curses.A_BOLD,
                "muted": curses.A_NORMAL,
            }
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        pair = 1
        for tone, (fg_name, bold) in _SEMANTIC_COLORS.items():
            fg = _COLOR_NAME_TO_CURSES.get(fg_name, -1)
            try:
                curses.init_pair(pair, fg, -1)
                attr = curses.color_pair(pair)
            except curses.error:
                attr = curses.A_NORMAL
            if bold:
                attr |= curses.A_BOLD
            self._attrs[tone] = attr
            pair += 1

    def attr(self, tone: str) -> int:
        return self._attrs.get(tone, curses.A_NORMAL)

class LauncherScreen:
    """Branded profile picker: titled list, ↑/↓ selection, ``q`` to quit.

    Always ends with a **Create New Player** CTA. Empty picker = CTA only (cold join).
    Broken profiles keep their ``error`` inline and use a warn tint when color is available.
    """

    def __init__(self, stdscr: curses.window, profiles: Sequence[ProfileRow] | None = None) -> None:
        self.stdscr = stdscr
        self.profiles: list[ProfileRow] = list(profiles or ())
        self.selected = 0  # index into selectable items (profiles + trailing CTA)
        self._palette = _TonePalette()
        self._chrome = self._palette.attr("info")
        self._warn = self._palette.attr("warn")
        self._ok = self._palette.attr("ok")
        self._muted = self._palette.attr("muted")

    def set_profiles(self, profiles: Sequence[ProfileRow]) -> None:
        self.profiles = list(profiles or ())
        self.selected = min(self.selected, max(0, self._n_items - 1))

    @property
    def _n_items(self) -> int:
        # profiles (0..n) + Create CTA as last selectable
        return len(self.profiles) + 1

    def _is_cta(self, index: int) -> bool:
        return index == len(self.profiles)

    def _row_base_attr(self, row: ProfileRow) -> int:
        if row.error:
            return self._warn
        if row.autopilot:
            return self._ok
        return self._muted

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        glyphs = _glyph_set()
        if max_y >= 3 and max_x >= 10:
            _draw_chrome_box(self.stdscr, self._chrome)
            _safe_addstr(self.stdscr, 0, 2, TITLE, self._chrome | curses.A_BOLD)
            _safe_addstr(self.stdscr, 1, 2, SUBTITLE, self._chrome)

        list_top = 3
        y = list_top

        # Column header when any healthy profile is present (chrome, not data).
        if self.profiles and any(not p.error for p in self.profiles) and y < max_y - 2:
            _safe_addstr(
                self.stdscr,
                y,
                5,
                f"{'name':<14} {'handle':<14} {'host':<22} game",
                self._chrome,
            )
            y += 1

        # Profile rows (including broken — never silently dropped).
        for i, row in enumerate(self.profiles):
            if y >= max_y - 2:
                break
            selected = i == self.selected
            prefix = f"{glyphs['sel']} " if selected else "  "
            base = self._row_base_attr(row)
            # A_REVERSE is the one selection convention — never a second scheme.
            attr = (base | curses.A_REVERSE) if selected else base
            if row.error:
                label = f"{row.name}  ·  ERROR: {row.error}"
                _safe_addstr(self.stdscr, y, 3, prefix + label, attr)
            else:
                host = row.host or row.server or "?"
                letter = (row.game_letter or "—")[:1]
                left = f"{row.name:<14} {row.handle:<14} {host:<22} "
                letter_attr = (attr | curses.A_BOLD) if selected else (base | curses.A_BOLD)
                x = 3
                _safe_addstr(self.stdscr, y, x, prefix + left, attr)
                x += len(prefix + left)
                _safe_addstr(self.stdscr, y, x, f"[{letter}]", letter_attr)
            y += 1

        # Create New Player CTA — sole content when the picker is empty.
        if y < max_y - 2:
            cta_index = len(self.profiles)
            selected = self.selected == cta_index
            attr = curses.A_REVERSE if selected else curses.A_BOLD
            prefix = f"{glyphs['sel']} " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + CREATE_CTA, attr)

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "↑/↓ select   Enter play/create   b bank   q quit",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``quit`` / ``create`` / ``play`` / ``bank`` / ``None``."""
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key in (ord("b"), ord("B")):
            return "bank"
        n = self._n_items
        if key in (curses.KEY_UP, ord("k")):
            self.selected = (self.selected - 1) % n
        elif key in (curses.KEY_DOWN, ord("j")):
            self.selected = (self.selected + 1) % n
        elif key in (curses.KEY_ENTER, 10, 13):
            if self._is_cta(self.selected):
                return "create"
            row = self.profiles[self.selected]
            if row.error:
                return None  # broken row stays on launcher
            return "play"
        return None

    def selected_profile(self) -> ProfileRow | None:
        if self._is_cta(self.selected) or not self.profiles:
            return None
        return self.profiles[self.selected]


PLAY_TITLE = " PLAY SHELL "
# Retained for import compatibility (tests/test_play_chrome_nav.py imports
# this name at module level) -- the chrome itself no longer draws this flat
# placeholder line; the GAME panel's own honest placeholder line replaces
# its purpose (PWO-031/033).
PLAY_SUBTITLE = " (placeholder — cockpit chrome is a later WO) "
BANK_TITLE = " PLAYER BANK "

# GAME panel content -- the live game viewport is a later WO (PREP §5); this
# is the honest placeholder canon calls for, never fake/invented content.
_GAME_PLACEHOLDER = "(placeholder — live game viewport wired in a later WO)"
# Empty-state fills for the PRIORITIES/HUD gutters before their data-source
# WOs land -- canon (trainer-cockpit.md "Panel states"): "PRIORITIES shows
# '—'"; HUD has no cited empty string at this reduced scope, so it gets the
# DoD's other approved honest-empty spelling to keep the two panels visibly
# distinct while both stay inside canon's stated vocabulary.
_PRIORITIES_EMPTY = "—"
_HUD_EMPTY = "(none yet)"
_LOGS_EMPTY = "(none yet)"
BOUNDARY_LINE_1 = (
    "Rotation multiplies YOUR own daily turns across INDEPENDENT characters."
)
BOUNDARY_LINE_2 = (
    "Hard line: never transfer credits/cargo/assets between them."
)


class PlayShellScreen:
    """Trainer-cockpit frame bound to one launcher profile (WO-P1-016,
    PWO-031/033).

    Renders the two-weight bordered chrome from
    ``cockpit.layout.frame_layout``: a cyan-bold double-line outer frame
    titled ``PLAY SHELL``, the row-1 character/profile strip
    (``cockpit.strip.compose_profile_strip_from_row``), a three-column body
    (thin-rounded PRIORITIES gutter | double-line GAME viewport | thin-rounded
    HUD gutter), and the bottom thin-rounded LOGS band carrying the
    ensure-session ``status_line``. The live game viewport itself is a later
    WO -- GAME always shows an honest placeholder line, never fake content.
    Below the fold floor (``mode == "too_small"``) only the layout's refusal
    message is drawn.

    Esc ends the binding and returns to the launcher — clean close, not a suspend.
    """

    def __init__(self, stdscr: curses.window, profile: ProfileRow) -> None:
        self.stdscr = stdscr
        self.profile = profile
        self.status_line = ""  # set by app.py after the ensure_session() call
        self._outer_attr = curses.A_NORMAL
        self._chrome_attr = curses.A_NORMAL
        self._init_colors()

    def _init_colors(self) -> None:
        if not curses.has_colors():
            # Monochrome: bold marks the outer frame apart from the thin
            # instrument chrome, same as the launcher's monochrome fallback.
            self._outer_attr = curses.A_BOLD
            self._chrome_attr = curses.A_NORMAL
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        # Cyan is chrome, never data (visual-language.md); the outer frame is
        # the one bold exception -- every other border/title stays non-bold
        # "info" tone so the eye lands on the game viewport, not the frame.
        self._chrome_attr = curses.color_pair(1)
        self._outer_attr = curses.color_pair(1) | curses.A_BOLD

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        regions = frame_layout(max_y, max_x)
        if regions["mode"] == "too_small":
            cockpit_draw.draw_refuse_message(self.stdscr, regions["message"], self._outer_attr)
            self.stdscr.refresh()
            return

        uok = cockpit_draw.unicode_ok()

        # Outer frame -- double-line, cyan+bold, titled on its own top-border
        # row (row 1 below it is fully claimed by the character/profile strip).
        cockpit_draw.draw_box(
            self.stdscr, regions["outer"], weight="double", attr=self._outer_attr,
            title=PLAY_TITLE.strip(), title_attr=self._outer_attr, uok=uok,
        )

        strip_region = regions["strip"]
        strip_text = compose_profile_strip_from_row(
            self.profile, width=strip_region["w"] if strip_region else 0, unicode_ok=uok
        )
        # Strip content is profile identity -- DATA, not chrome. Canon
        # doctrine ("cyan is chrome, never data", visual-language.md) reads
        # as an interim ruling here pending hub ratification of this
        # concept's own promotion out of staged status; A_NORMAL (default
        # fg, non-bold) keeps the row itself un-tinted while the outer
        # frame's own border stays cyan around it.
        cockpit_draw.draw_lines(self.stdscr, strip_region, [strip_text], curses.A_NORMAL, boxed=False)

        left = regions["left_gutter"]
        cockpit_draw.draw_box(
            self.stdscr, left, weight="thin", attr=self._chrome_attr,
            title="PRIORITIES", title_attr=self._chrome_attr, uok=uok,
        )
        cockpit_draw.draw_lines(self.stdscr, left, [_PRIORITIES_EMPTY], curses.A_NORMAL)

        center = regions["center"]
        if center is not None:
            if center["border"]:
                cockpit_draw.draw_box(
                    self.stdscr, center, weight="double", attr=self._chrome_attr,
                    title="GAME", title_attr=self._chrome_attr, uok=uok,
                )
                cockpit_draw.draw_lines(self.stdscr, center, [_GAME_PLACEHOLDER], curses.A_NORMAL)
            else:
                cockpit_draw.draw_lines(
                    self.stdscr, center, [_GAME_PLACEHOLDER], curses.A_NORMAL, boxed=False
                )

        right = regions["right_gutter"]
        cockpit_draw.draw_box(
            self.stdscr, right, weight="thin", attr=self._chrome_attr,
            title="HUD", title_attr=self._chrome_attr, uok=uok,
        )
        cockpit_draw.draw_lines(self.stdscr, right, [_HUD_EMPTY], curses.A_NORMAL)

        logs = regions["logs"]
        cockpit_draw.draw_box(
            self.stdscr, logs, weight="thin", attr=self._chrome_attr,
            title="LOGS", title_attr=self._chrome_attr, uok=uok,
        )
        cockpit_draw.draw_lines(
            self.stdscr, logs, [self.status_line or _LOGS_EMPTY], curses.A_NORMAL
        )

        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``back`` / ``quit`` / ``None``."""
        if key == 27:  # Esc — end binding, return to launcher
            return "back"
        if key in (ord("q"), ord("Q")):
            return "quit"
        return None


class BankViewScreen:
    """Credential-bank rotation touchpoint — metadata only (WO-P1-015)."""

    def __init__(
        self,
        stdscr: curses.window,
        entries: Sequence[dict[str, str]] | None = None,
    ) -> None:
        self.stdscr = stdscr
        self.entries = list(entries or ())
        self._chrome = curses.A_NORMAL
        self._warn = curses.A_BOLD
        self._init_colors()

    def _init_colors(self) -> None:
        if not curses.has_colors():
            self._chrome = curses.A_BOLD
            self._warn = curses.A_BOLD | curses.A_UNDERLINE
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        self._chrome = curses.color_pair(1)
        self._warn = curses.color_pair(2) | curses.A_BOLD

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        if max_y >= 3 and max_x >= 10:
            try:
                self.stdscr.attron(self._chrome)
                self.stdscr.box()
                self.stdscr.attroff(self._chrome)
            except curses.error:
                pass
            _safe_addstr(self.stdscr, 0, 2, TITLE, self._chrome | curses.A_BOLD)
            _safe_addstr(self.stdscr, 1, 2, BANK_TITLE, self._chrome)

        # Boundary shown at the touchpoint — never buried.
        _safe_addstr(self.stdscr, 2, 3, BOUNDARY_LINE_1, self._warn)
        _safe_addstr(self.stdscr, 3, 3, BOUNDARY_LINE_2, self._warn)

        y = 5
        header = (
            f"{'name':<16} {'handle':<16} {'host':<24} "
            f"{'game':<3} {'last_played':<21} turns"
        )
        _safe_addstr(self.stdscr, y, 3, header, self._chrome)
        y += 1
        if not self.entries:
            _safe_addstr(
                self.stdscr,
                y,
                3,
                "(bank empty — add profiles; rotation history shows never / -)",
                curses.A_DIM,
            )
        else:
            for entry in self.entries:
                if y >= max_y - 2:
                    break
                line = (
                    f"{entry.get('name', '?'):<16} "
                    f"{entry.get('handle', '?'):<16} "
                    f"{entry.get('host', '?'):<24} "
                    f"{entry.get('game_letter', '?'):<3} "
                    f"{entry.get('last_played', 'never'):<21} "
                    f"{entry.get('turns_state', '-')}"
                )
                _safe_addstr(self.stdscr, y, 3, line, curses.A_NORMAL)
                y += 1

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "Esc return to launcher",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        if key == 27:
            return "back"
        if key in (ord("q"), ord("Q")):
            return "quit"
        return None


# Field kinds on the create form (server picker + two text fields). No secret fields.
_FORM_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("server", "Server", "server"),
    ("game_letter", "Game letter", "text"),
    ("handle", "Handle", "text"),
)


def validate_create_form(
    *,
    server: str,
    game_letter: str,
    handle: str,
    catalog_keys: Sequence[str] | None = None,
    existing_names: Sequence[str] | None = None,
) -> str | None:
    """UI-side create-form checks. Return an error string, or ``None`` if ok.

    Does not write. Rejects empty game letter, unknown catalog server keys, and
    duplicate profile section names (derived from handle when name is omitted).
    """
    game = (game_letter or "").strip()
    if not game:
        return "game letter required"
    handle_s = (handle or "").strip()
    if not handle_s:
        return "handle required"
    key = (server or "").strip()
    if not key:
        return "server catalog key required"
    keys = set(catalog_keys) if catalog_keys is not None else {
        str(s["key"]) for s in credentials.list_servers()
    }
    if key not in keys:
        return f"unknown server catalog key: {key!r}"
    section = re.sub(r"[^a-z0-9]+", "_", handle_s.lower()).strip("_") or "profile"
    names = (
        set(existing_names)
        if existing_names is not None
        else {str(r["name"]) for r in credentials.list_profile_summaries()}
    )
    if section in names:
        return f"profile already exists: {section}"
    return None


class CreateFormScreen:
    """Catalog server + game_letter + handle → non-secret ``create_profile`` write."""

    def __init__(self, stdscr: curses.window) -> None:
        self.stdscr = stdscr
        self.servers = credentials.list_servers()
        self.server_idx = 0
        self.values = {
            "game_letter": "B",
            "handle": "",
        }
        self.focus = 0
        self.editing = False
        self.edit_buf = ""
        self.error = ""
        self._chrome = curses.A_NORMAL
        self._warn = curses.A_BOLD
        self._init_colors()

    def _init_colors(self) -> None:
        if not curses.has_colors():
            self._chrome = curses.A_BOLD
            self._warn = curses.A_BOLD | curses.A_UNDERLINE
            return
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        self._chrome = curses.color_pair(1)
        self._warn = curses.color_pair(2) | curses.A_BOLD

    def _server_key(self) -> str:
        if not self.servers:
            return ""
        return str(self.servers[self.server_idx]["key"])

    def _server_label(self) -> str:
        if not self.servers:
            return "(no servers in catalog)"
        row = self.servers[self.server_idx]
        return f"{row['key']}  ·  {row['name']}"

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        if max_y >= 3 and max_x >= 10:
            try:
                self.stdscr.attron(self._chrome)
                self.stdscr.box()
                self.stdscr.attroff(self._chrome)
            except curses.error:
                pass
            _safe_addstr(self.stdscr, 0, 2, TITLE, self._chrome | curses.A_BOLD)
            _safe_addstr(self.stdscr, 1, 2, CREATE_TITLE, self._chrome)

        if self.error:
            _safe_addstr(self.stdscr, 2, 3, f"! {self.error}", self._warn)

        for i, (key, label, kind) in enumerate(_FORM_FIELDS):
            y = 4 + i
            if y >= max_y - 2:
                break
            selected = i == self.focus
            attr = curses.A_REVERSE if selected and not self.editing else curses.A_NORMAL
            if kind == "server":
                shown = self._server_label()
            else:
                shown = self.values[key]
                if self.editing and selected:
                    shown = self.edit_buf + "_"
            line = f"{label:<14} {shown}"
            prefix = "▸ " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + line, attr)

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "↑/↓ field  ←/→ server  e/Enter edit  s save  Esc cancel",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``saved`` / ``cancel`` / ``None``."""
        field_key, _label, kind = _FORM_FIELDS[self.focus]

        if self.editing:
            if key == 27:  # Esc
                self.editing = False
                try:
                    curses.curs_set(0)
                except curses.error:
                    pass
            elif key in (curses.KEY_ENTER, 10, 13):
                value = self.edit_buf.strip()
                if field_key == "game_letter":
                    value = value.upper()[:1]
                self.values[field_key] = value
                self.editing = False
                try:
                    curses.curs_set(0)
                except curses.error:
                    pass
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                self.edit_buf = self.edit_buf[:-1]
            elif 32 <= key < 127:
                self.edit_buf += chr(key)
            return None

        if key in (27, ord("q"), ord("Q")):
            return "cancel"
        if key in (curses.KEY_UP, ord("k")):
            self.focus = (self.focus - 1) % len(_FORM_FIELDS)
        elif key in (curses.KEY_DOWN, ord("j")):
            self.focus = (self.focus + 1) % len(_FORM_FIELDS)
        elif key == ord("s"):
            return self._try_save()
        elif kind == "server" and key in (curses.KEY_LEFT, ord("h")):
            if self.servers:
                self.server_idx = (self.server_idx - 1) % len(self.servers)
        elif kind == "server" and key in (
            curses.KEY_RIGHT,
            ord("l"),
            curses.KEY_ENTER,
            10,
            13,
            ord(" "),
        ):
            if self.servers:
                self.server_idx = (self.server_idx + 1) % len(self.servers)
        elif kind == "text" and key in (ord("e"), curses.KEY_ENTER, 10, 13):
            self.editing = True
            self.edit_buf = self.values[field_key]
            try:
                curses.curs_set(1)
            except curses.error:
                pass
        return None

    def _try_save(self) -> str | None:
        # Snapshot field values first — a reject must leave them intact for correction.
        server = self._server_key()
        game_letter = self.values["game_letter"]
        handle = self.values["handle"]
        catalog_keys = [str(s["key"]) for s in self.servers]
        err = validate_create_form(
            server=server,
            game_letter=game_letter,
            handle=handle,
            catalog_keys=catalog_keys,
        )
        if err:
            self.error = err
            # Values untouched — operator corrects the bad field only.
            return None
        try:
            credentials.create_profile(
                server=server,
                game_letter=game_letter,
                handle=handle,
            )
        except Exception as exc:  # noqa: BLE001 — surface in TUI; values preserved
            self.error = str(exc)
            return None
        return "saved"
