"""Create-profile form screen (extracted from ``screens`` — WO-SCREENS-CREATE-FORM-SPLIT).

Credentials/secrets are never collected or shown on this surface.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

import curses

from tw2002_aiclient.screens import CREATE_TITLE, TITLE, _TonePalette, _safe_addstr
from tw2002_aiclient.session import credentials

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


def _create_error_text(exc: Exception) -> str:
    """Operator-facing text for a rejected create-save.

    A store-read failure is rendered from its OWN fields, never from
    ``str(exc)``. ``credentials._StoreReadFailure.__init__`` appends the
    store's full absolute path to the message, and this text is drawn as one
    line at column 3, which ``cockpit.draw.safe_write`` clips to ``max_x -
    x`` -- 77 cells on an 80-column form. Measured against a 51-character
    store path, the corrupt and malformed messages render 103 and 90 cells;
    a deeper install path overflows the denied one (73) as well.

    The overflow is not merely cosmetic. The line is clipped from the RIGHT,
    so the first thing to fall off is the store's BASENAME -- which is the
    "WHICH of the two stores failed" that the path was being carried for in
    the first place. The abs-path spelling is the one spelling of that
    answer which cannot reliably fit on the screen it is written to.

    So this renders the same two fields ``credentials._store_failure_row``
    puts in the launcher's row, in that function's own spellings -- the
    store's FILE NAME (the resolver reads two stores; ``path`` exists to say
    which) and ``cause: reason``. That function's docstring already made
    this call for its surface ("carries ``reason`` and not ``str(exc)``…
    Callers that want the path have the exception"); the create form is the
    adjacent surface rendering the identical failure, and it now agrees.

    Everything else keeps ``str(exc)`` verbatim -- deliberately NOT a
    blanket path-strip. ``create_profile``'s own ``ValueError``s ("unknown
    server catalog key: 'demo'", "profile already exists: alpha") ARE the
    operator's next action, and they carry no path to begin with.
    """
    if isinstance(
        exc, (credentials.ProfileStoreUnreadable, credentials.ProfileStoreMalformed)
    ):
        # The two (and only two) `_StoreReadFailure` subclasses -- named as
        # the public pair, matching `credentials.list_profile_summaries`'
        # own catch, rather than reaching for the private mixin.
        return f"({Path(exc.path).name}) {exc.cause}: {exc.reason}"
    return str(exc)


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
        # Reuses _TonePalette -- see BankViewScreen._init_colors' own
        # comment (WO-P3-040 REVISE, Mack single-source MEDIUM + CRITICAL
        # pair-collision fix); identical "chrome"/"warn" mapping and
        # byte-identical monochrome fallback, zero visible behavior change.
        palette = _TonePalette()
        self._chrome = palette.attr("info")
        self._warn = palette.attr("warn")

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
            # Still the widest possible catch, and still nothing but a
            # message assignment: a form that raises loses the operator's
            # typed input. Only the RENDERING moved -- see _create_error_text.
            self.error = _create_error_text(exc)
            return None
        return "saved"
