"""Pre-cockpit launcher + create-profile form (WO-P1-010…012).

Credentials/secrets are never collected or shown on these surfaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

import curses

from tw2002_aiclient.session import credentials


@dataclass(frozen=True)
class ProfileRow:
    """Non-secret profile summary for the picker (name/handle/server only)."""

    name: str
    handle: str
    server: str
    game_letter: str = ""
    error: str | None = None  # parse failure — row stays visible (never dropped)


TITLE = " TW2002 AICLIENT "
SUBTITLE = " SELECT PROFILE "
CREATE_CTA = "Create New Player"
CREATE_TITLE = " CREATE NEW PLAYER "


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


class LauncherScreen:
    """Branded profile picker: titled list, ↑/↓ selection, ``q`` to quit.

    Always ends with a **Create New Player** CTA. Empty picker = CTA only (cold join).
    Broken profiles keep their ``error`` inline and use a warn tint when color is available.
    """

    def __init__(self, stdscr: curses.window, profiles: Sequence[ProfileRow] | None = None) -> None:
        self.stdscr = stdscr
        self.profiles: list[ProfileRow] = list(profiles or ())
        self.selected = 0  # index into selectable items (profiles + trailing CTA)
        self._chrome = curses.A_NORMAL
        self._warn = curses.A_BOLD
        self._init_colors()

    def set_profiles(self, profiles: Sequence[ProfileRow]) -> None:
        self.profiles = list(profiles or ())
        self.selected = min(self.selected, max(0, self._n_items - 1))

    @property
    def _n_items(self) -> int:
        # profiles (0..n) + Create CTA as last selectable
        return len(self.profiles) + 1

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

    def _is_cta(self, index: int) -> bool:
        return index == len(self.profiles)

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
            _safe_addstr(self.stdscr, 1, 2, SUBTITLE, self._chrome)

        list_top = 3
        y = list_top

        # Profile rows (including broken — never silently dropped).
        for i, row in enumerate(self.profiles):
            if y >= max_y - 2:
                break
            selected = i == self.selected
            if row.error:
                label = f"{row.name}  ·  ERROR: {row.error}"
                base = self._warn
            else:
                label = f"{row.name}  ·  {row.handle}  ·  {row.server}"
                if row.game_letter:
                    label += f"  [{row.game_letter}]"
                base = curses.A_NORMAL
            attr = (base | curses.A_REVERSE) if selected else base
            prefix = "▸ " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + label, attr)
            y += 1

        # Create New Player CTA — sole content when the picker is empty.
        if y < max_y - 2:
            cta_index = len(self.profiles)
            selected = self.selected == cta_index
            attr = curses.A_REVERSE if selected else curses.A_BOLD
            prefix = "▸ " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + CREATE_CTA, attr)

        _safe_addstr(
            self.stdscr,
            max_y - 2,
            3,
            "↑/↓ select   Enter open   q quit",
            self._chrome,
        )
        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``quit`` / ``create`` / ``None``."""
        if key in (ord("q"), ord("Q")):
            return "quit"
        n = self._n_items
        if key in (curses.KEY_UP, ord("k")):
            self.selected = (self.selected - 1) % n
        elif key in (curses.KEY_DOWN, ord("j")):
            self.selected = (self.selected + 1) % n
        elif key in (curses.KEY_ENTER, 10, 13):
            if self._is_cta(self.selected):
                return "create"
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
