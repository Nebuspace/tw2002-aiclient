"""Pre-cockpit launcher + create-profile form (WO-P1-010…012).

Credentials/secrets are never collected or shown on these surfaces.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Sequence

import curses

from tw2002_aiclient import chain_status as _chain_status
from tw2002_aiclient import focus_status as _focus_status
from tw2002_aiclient import world_stats as _world_stats
from tw2002_aiclient.cockpit import analyze as cockpit_analyze
from tw2002_aiclient.cockpit import armconfirm as cockpit_armconfirm
from tw2002_aiclient.cockpit import autoloop_controls as cockpit_autoloop_controls
from tw2002_aiclient.cockpit import chain_bubbles as cockpit_chain_bubbles
from tw2002_aiclient.cockpit import chains as cockpit_chains
from tw2002_aiclient.cockpit import control_seat as cockpit_control_seat
from tw2002_aiclient.cockpit import covermeter as cockpit_covermeter
from tw2002_aiclient.cockpit import reflex_controls as cockpit_reflex_controls
from tw2002_aiclient.cockpit import rules_library as cockpit_rules_library
from tw2002_aiclient.cockpit import decisions as cockpit_decisions
from tw2002_aiclient.cockpit import draft_approve as cockpit_draft_approve
from tw2002_aiclient.cockpit import draw as cockpit_draw
from tw2002_aiclient.cockpit import focus as cockpit_focus
from tw2002_aiclient.cockpit import fold as cockpit_fold
from tw2002_aiclient.cockpit import formations as cockpit_formations
from tw2002_aiclient.cockpit import goals as cockpit_goals
from tw2002_aiclient.cockpit import hud as cockpit_hud
from tw2002_aiclient.cockpit import liveness as cockpit_liveness
from tw2002_aiclient.cockpit import logsband as cockpit_logsband
from tw2002_aiclient.cockpit import stopbanner as cockpit_stopbanner
from tw2002_aiclient.cockpit import teachband as cockpit_teachband
from tw2002_aiclient.cockpit import tones as cockpit_tones
from tw2002_aiclient.cockpit import viewport as cockpit_viewport
from tw2002_aiclient.cockpit import viewport_color as cockpit_viewport_color
from tw2002_aiclient.cockpit.layout import frame_layout, nested_focus_region
from tw2002_aiclient.cockpit.strip import compose_profile_strip_segments_from_row
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
    # Read-only daemon presence overlay (never from config; exact profile match).
    online: bool = False


TITLE = " TW2002 AICLIENT "
SUBTITLE = " SELECT PROFILE "
CREATE_CTA = "Create New Player"
CREATE_TITLE = " CREATE NEW PLAYER "

# Shared 7-tone table -- SOURCED FROM cockpit.tones.SEMANTIC_COLORS (WO-P3-040
# single source of truth). screens.py used to fork its own literal copy of
# this table; every curses-facing consumer here (LauncherScreen's
# _TonePalette, PlayShellScreen's chrome/viewport-border colors) now resolves
# tone names off cockpit.tones directly, so a tone-table edit there needs no
# echo here. Values stay the pure (curses_fg_name, bold) shape tones.py
# defines; "muted" = terminal default, non-bold.
_SEMANTIC_COLORS: dict[str, tuple[str, bool]] = cockpit_tones.SEMANTIC_COLORS

_COLOR_NAME_TO_CURSES = {
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "red": curses.COLOR_RED,
    "cyan": curses.COLOR_CYAN,
    "default": -1,
    # GAME-cell vocabulary (WO-P4-053 draw-seam merge) -- pyte's own color
    # names, sourced from cockpit.viewport_color.PYTE_TO_CURSES_COLOR
    # rather than re-declared here, so that table stays the one source of
    # truth for "pyte name -> curses int". "brown" is pyte's own ANSI-
    # yellow quirk (see that module's docstring); chrome's tone table never
    # emits it (tones.py uses the plain string "yellow" instead), so the
    # two vocabularies add up with no colliding key, both resolving the
    # same COLOR_YELLOW int under their own distinct name.
    **cockpit_viewport_color.PYTE_TO_CURSES_COLOR,
}

_UNSET = object()  # cache-miss sentinel -- distinguishes "never attempted" from "cached failure" (None)


class _SharedPairs:
    """Process-lifetime curses color-pair allocator -- the ONLY place
    ``curses.init_pair``/``curses.start_color`` are called anywhere in this
    module (WO-P3-040 REVISE, Mack CRITICAL finding).

    ``curses`` color-pair NUMBERS are global to the whole terminal session,
    not scoped per class or per screen instance. Before this fix, every
    screen in this file hardcoded its OWN pair numbers with DIFFERENT
    colors: ``_TonePalette`` (the launcher's 7-tone palette) allocated
    pairs 1-7 sequentially at construction; ``PlayShellScreen``,
    ``BankViewScreen``, and ``CreateFormScreen`` each separately called
    ``curses.init_pair(1, ...)``/``curses.init_pair(2, ...)`` with their own
    colors. Constructing a SECOND screen mid-session silently
    **re-painted** whatever pair number(s) it happened to reuse -- and a
    curses attr int returned by ``curses.color_pair(n)`` only encodes the
    pair NUMBER, resolved to an actual color by the terminal at RENDER
    time, never at the moment the attr int was computed. So a
    previously-constructed screen's ALREADY-CACHED attr ints (e.g.
    ``LauncherScreen``'s ``self._ok``/``self._warn``, set once in
    ``__init__``) silently changed color out from under it the instant any
    other screen reused that pair number for something else. Reproduced:
    a launcher -> play -> Esc -> back round trip permanently repainted the
    SAME launcher instance's warn row red and its ok row cyan for the rest
    of the process (Mack's PoC) -- because ``PlayShellScreen`` happened to
    reuse pairs 1/2 for its own info/danger colors.

    The fix: exactly ONE process-lifetime allocator (this class, and the
    module-level ``_shared_pairs`` instance below). It allocates a pair
    number PER DISTINCT COLOR COMBINATION on first request, caches it
    forever, and every later request for that same combination returns the
    SAME pair number -- so no two screens can ever collide, no matter how
    many are constructed across the app's lifetime, and no matter which
    order. Two tones that happen to share a combination (``"ok"``/``"gain"``
    both ``("green", "default")``, ``"danger"``/``"loss"`` both
    ``("red", "default")``) now legitimately share ONE underlying pair too
    -- a pure allocation-count optimization, not a behavior change, since
    callers still apply their own bold flag on top of the returned base
    attr.

    WO-P4-053 draw-seam merge: the cache key widened from a bare ``str``
    fg-color-name to a ``tuple[str, str]`` ``(fg_name, bg_name)`` so the
    GAME viewport's per-cell colors (which need a real ``bg``, e.g. a
    highlighted status line) can share this SAME allocator instead of a
    second, independently-counting one -- two allocators would reopen the
    exact pair-number-collision bug this class exists to eliminate, this
    time between chrome and game cells rather than between two screens.
    Every existing single-name chrome caller (``attr_for(fg_name)``) is
    unaffected: ``bg_name`` defaults to ``"default"``, which resolves to
    curses' ``-1`` sentinel exactly like the old hardcoded
    ``curses.init_pair(pair_n, fg, -1)`` did, so chrome's cache keys,
    allocated pair numbers, and returned attrs are byte-for-byte identical
    to before this widening.

    This merge also absorbed ``cockpit.viewport_color``'s reference
    ``GameCellPairs`` (now deleted -- a second live allocator was never
    meant to ship) along with its two hardening upgrades, applied here for
    every caller, chrome included: a proactive ``curses.COLOR_PAIRS`` bound
    check (skip the doomed ``init_pair`` call entirely once the table is
    known-full) and CACHING a failed allocation rather than retrying it on
    every call. ``COLOR_PAIRS`` is a fixed terminal capability for the
    process's lifetime, so a failure can never later succeed -- retrying
    it as a ``curses.error`` exception on every single call would be
    needless overhead, harmless for chrome's handful of one-time
    construction-time lookups but real waste for GAME-cell resolution,
    which runs once per colored run, per redraw, of a live scrolling
    screen.
    """

    def __init__(self) -> None:
        self._pair_for_key: dict[tuple[str, str], int | None] = {}
        self._next_pair = 1
        self._started = False

    def attr_for(self, fg_name: object, bg_name: object = "default") -> int:
        """Base (non-bold) curses attr for the ``(fg_name, bg_name)``
        color-name combination. ``bg_name`` defaults to ``"default"`` for
        chrome's existing single-name callers (zero behavior change --
        see the class docstring). ``"default"`` (or any name absent from
        ``_COLOR_NAME_TO_CURSES``, including a hostile non-``str`` name)
        means terminal-default for that side, NOT a forced color -- if
        BOTH sides resolve to default, nothing is colored at all and no
        pair is allocated for it. Never raises: no color support, an
        exhausted pair table (checked proactively via
        ``curses.COLOR_PAIRS`` when available, and reactively via a
        ``curses.error`` catch around ``curses.init_pair`` either way), or
        any other curses failure all degrade this call to
        ``curses.A_NORMAL`` rather than crashing the draw pass, the same
        honesty-over-crash convention every other curses-facing call in
        this module already follows."""
        if not curses.has_colors():
            return curses.A_NORMAL
        fg = _COLOR_NAME_TO_CURSES.get(fg_name, -1) if isinstance(fg_name, str) else -1
        bg = _COLOR_NAME_TO_CURSES.get(bg_name, -1) if isinstance(bg_name, str) else -1
        if fg == -1 and bg == -1:
            return curses.A_NORMAL

        # Hostile non-str names already collapsed to -1 above; normalize
        # the CACHE key the same way so it stays a plain, always-hashable
        # (str, str) tuple regardless of what was actually passed in (a
        # hostile unhashable fg_name/bg_name -- e.g. a list -- must never
        # reach a dict-key position).
        fg_key = fg_name if isinstance(fg_name, str) else "default"
        bg_key = bg_name if isinstance(bg_name, str) else "default"
        key = (fg_key, bg_key)

        cached = self._pair_for_key.get(key, _UNSET)
        if cached is not _UNSET:
            return curses.A_NORMAL if cached is None else curses.color_pair(cached)

        if not self._started:
            try:
                curses.start_color()
            except curses.error:
                pass
            try:
                curses.use_default_colors()
            except curses.error:
                pass
            self._started = True

        limit = getattr(curses, "COLOR_PAIRS", None)
        if limit is not None and self._next_pair >= limit:
            self._pair_for_key[key] = None
            return curses.A_NORMAL

        pair_n = self._next_pair
        try:
            curses.init_pair(pair_n, fg, bg)
        except curses.error:
            self._pair_for_key[key] = None
            return curses.A_NORMAL
        self._next_pair += 1
        self._pair_for_key[key] = pair_n
        return curses.color_pair(pair_n)


# One process-lifetime allocator shared by every screen in this module --
# see _SharedPairs' own docstring for why a per-class allocator corrupted
# other screens' already-cached colors.
_shared_pairs = _SharedPairs()

# Thin-rounded HUD chrome (launcher has no live viewport — never double-line).
# Per WO-AUDIT-GLYPH-TABLE-DEDUPE: cockpit.draw's THIN_UNICODE/THIN_ASCII are
# THE single source for the six box-drawing keys (tl/tr/bl/br/h/v) — imported
# and extended here, never re-typed, so the two tables cannot drift. ``sel``
# is the launcher's own addition on top: the cockpit chrome has no
# selection-triangle concept, only the launcher's row-picker does.
_GLYPHS_UNICODE = {**cockpit_draw.THIN_UNICODE, "sel": "▸"}
_GLYPHS_ASCII = {**cockpit_draw.THIN_ASCII, "sel": ">"}


def _unicode_ok() -> bool:
    """Thin delegate onto ``cockpit.draw.unicode_ok`` (WO-AUDIT-UNICODE-OK-
    DOCSTRING) -- this used to be a second, independent copy of the same
    predicate, and its docstring had drifted to promise an "otherwise prefer
    UTF-8-capable locale" fallback that the code never performed. There is no
    locale inspection here or in ``draw``: ASCII is forced ONLY when
    ``TW2002_ASCII`` strips to exactly ``"1"``; EVERY other value -- unset,
    empty, ``"0"``, ``"01"``, ``"true"`` -- yields Unicode. Kept as a local
    name so ``_glyph_set()`` below stays untouched.
    """
    return cockpit_draw.unicode_ok()


def _glyph_set() -> dict[str, str]:
    return _GLYPHS_UNICODE if _unicode_ok() else _GLYPHS_ASCII


def _safe_addstr(win: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    """Thin delegate onto ``cockpit.draw.safe_write`` (WO-AUDIT-SAFE-ADDSTR-
    DEDUPE) -- this used to be a separate, less-hardened local write
    primitive; it is now the SAME choke every cockpit panel writes through,
    kept as a local name so every launcher/bank/create-form call site below
    (including the operator-typed ``edit_buf`` live-echo at the create form)
    stays untouched. Two deliberate hardening-parity behavior changes this
    brings to the launcher family, versus the old local clip:
    (a) control characters in the written text are now neutralized to a
    plain space before the write, where they previously reached ``addstr``
    raw -- this is the path that renders the operator's own live-typed
    field echo, so a raw control byte typed into a field could previously
    move the real terminal cursor;
    (b) text may now occupy the window's true last column, with the
    resulting bottom-right-cell ``curses.error`` caught and ignored, where
    the old clip stopped one column short of the window edge unconditionally.
    Neither is a functional regression -- see ``cockpit.draw``'s own module
    docstring for why both are the correct, already-proven behavior."""
    cockpit_draw.safe_write(win, y, x, text, attr)


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
        # Colors resolve through the ONE shared process-lifetime allocator
        # (WO-P3-040 REVISE, Mack CRITICAL) -- no init_pair call here
        # anymore. See _SharedPairs' own docstring for why a per-class
        # allocator corrupted other screens' already-cached colors.
        for tone, (fg_name, bold) in _SEMANTIC_COLORS.items():
            attr = _shared_pairs.attr_for(fg_name)
            if bold:
                attr |= curses.A_BOLD
            self._attrs[tone] = attr

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
        self.presence_note: str | None = None  # honest unavailable / status copy
        self._palette = _TonePalette()
        self._chrome = self._palette.attr("info")
        self._warn = self._palette.attr("warn")
        self._ok = self._palette.attr("ok")
        self._muted = self._palette.attr("muted")
        self._danger = self._palette.attr("danger")

    def set_profiles(self, profiles: Sequence[ProfileRow]) -> None:
        self.profiles = list(profiles or ())
        self.selected = min(self.selected, max(0, self._n_items - 1))

    def set_presence_note(self, note: str | None) -> None:
        self.presence_note = note if isinstance(note, str) and note.strip() else None

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
                f"{'name':<14} {'handle':<14} {'host':<22} game   status",
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
                x += len(f"[{letter}]")
                if row.online:
                    # Presence is exact-match only; ok tone, never inferred.
                    online_attr = (self._ok | curses.A_REVERSE) if selected else self._ok
                    _safe_addstr(self.stdscr, y, x, "  ONLINE", online_attr | curses.A_BOLD)
            y += 1

        # Create New Player CTA — sole content when the picker is empty.
        if y < max_y - 2:
            cta_index = len(self.profiles)
            selected = self.selected == cta_index
            attr = curses.A_REVERSE if selected else curses.A_BOLD
            prefix = f"{glyphs['sel']} " if selected else "  "
            _safe_addstr(self.stdscr, y, 3, prefix + CREATE_CTA, attr)

        hint_y = max_y - 2
        if self.presence_note and hint_y > 0:
            _safe_addstr(self.stdscr, hint_y - 1, 3, self.presence_note, self._warn)
        _safe_addstr(
            self.stdscr,
            hint_y,
            3,
            "↑/↓ select   Enter play/create   b bank   q quit",
            self._chrome,
        )
        self.stdscr.refresh()

    def draw_quit_confirm(self, line: str) -> None:
        """Draw the whole-app exit confirm (danger + reverse; not money-path copy)."""
        self.draw()
        max_y, _max_x = self.stdscr.getmaxyx()
        text = " ".join(str(line).split()) if line else ""
        if text and max_y >= 2:
            attr = self._danger | curses.A_BOLD | curses.A_REVERSE
            _safe_addstr(self.stdscr, max_y - 2, 3, text, attr)
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
# placeholder line; the GAME panel itself now draws an honest blank grid
# (PWO-051) rather than any placeholder text (PWO-031/033).
PLAY_SUBTITLE = " (placeholder — cockpit chrome is a later WO) "
BANK_TITLE = " PLAYER BANK "

# The bank view's two negatives, kept apart on screen because they are not the
# same fact (WO-AUDIT-PLAYER-BANK-STORE-HONESTY). BANK_EMPTY_LINE is a claim --
# "we read the bank and there is nothing in it" -- and only a successful read
# earns it. BANK_UNREADABLE_* say the opposite: nothing was read, so no listing
# and no count (not even zero) may be shown, because a count is a claim about
# contents nobody saw. The reason line carries the operator's next action; see
# player_bank.BankUnreadable's CAUSE_* vocabulary.
BANK_EMPTY_LINE = "(bank empty — add profiles; rotation history shows never / -)"
BANK_UNREADABLE_HEAD = "bank could not be read — this is NOT an empty bank"
BANK_UNREADABLE_HINT = "no character list and no count can be shown: nothing here was read"

# A raising composer (bad input surviving to a status field, a future
# panel's own bug, ...) must never take the whole cockpit down with it --
# same honesty-over-crash fallback as an unreachable/raising status_provider
# (Mack finding: the provider call was already guarded, the compose call
# wasn't). One honest-unknown line per panel, reusing the established
# em-dash glyph rather than inventing a second "something broke" vocabulary.
_GOALS_COMPOSE_FAILED = ["—"]
_FOCUS_COMPOSE_FAILED = ["—"]
_FORMATIONS_COMPOSE_FAILED = ["—"]
# DECISIONS' own composer already defines its honest-empty state as
# ``["—", "Exploring…"]`` (canon `trainer-cockpit.md` "Panel states":
# `DECISIONS shows ["—", "Exploring…"]`) -- the raising-composer fallback
# mirrors that same two-line shape rather than the other panels' bare
# em-dash, so a compose-time crash still reads as "known-nothing, not a
# bug" instead of visibly regressing to a shorter, differently-shaped panel.
_DECISIONS_COMPOSE_FAILED = ["—", "Exploring…"]
# The responsive-fold composer (WO-P3-039, ``cockpit.fold.
# compose_folded_decisions_lines``) defines its own all-empty state as the
# same two-line ``["—", "Exploring…"]`` shape as unfolded DECISIONS (the
# fold relocates GOALS+FOCUS content INTO the DECISIONS pane; it does not
# invent a third empty-state vocabulary). A raising fold composer falls
# back to the single em-dash line GOALS/FOCUS already use, not the two-line
# shape -- a compose-time crash on the folded path is closer in spirit to
# "one of several stacked sections failed" than "the whole panel is
# honestly idle", so it reuses the plainer single-line fallback rather than
# claiming the two-line honest-empty state that the real composer reserves
# for "no data was folded in at all".
_FOLD_COMPOSE_FAILED = ["—"]
# HUD's own composer (PWO-037, ``cockpit.hud.compose_hud_cells``) already
# defines its own honest-empty state -- every cell sticky ``"-"`` with no
# freshness stamp, per-CELL rather than per-panel (canon
# `trainer-cockpit.md` "The always-on HUD and its freshness": a cold cell
# persists "-", never blank). The raising-composer fallback below is HUD's
# own ``(text, stale)`` cell shape, not the plain string list GOALS/FOCUS/
# DECISIONS use -- one honest-unknown, never-stale cell, reusing that same
# plain-hyphen vocabulary rather than the other panels' em-dash (HUD's
# sticky-unknown glyph is "-", not "—" -- ``cockpit.hud``'s own convention,
# distinct on purpose).
_HUD_COMPOSE_FAILED = [("-", False)]
# CONTROL_STRIP's own composer (WO-P3-038, ``cockpit.liveness.
# compose_liveness_cluster``) has no honest-empty convention of its own to
# borrow -- it is a bare motion cluster, not a panel with an empty state --
# so a raising composer falls back to the empty string (renders as a blank
# row this tick) rather than any invented placeholder text.
_CONTROL_STRIP_COMPOSE_FAILED = ""
# LOGS' own composer (WO-P3-041, ``cockpit.logsband.compose_logs_lines``)
# already defines its own single-line honest-empty state
# (``cockpit_logsband.LOGS_EMPTY``) -- a raising composer reuses that exact
# text rather than the other panels' em-dash, since LOGS never had an
# em-dash "unknown" vocabulary to begin with (its own honest-empty already
# reads as "known-nothing, not a bug"). Sliced to whatever height actually
# fits at draw time -- see ``draw()``'s own LOGS block.
_LOGS_COMPOSE_FAILED = [cockpit_logsband.LOGS_EMPTY]
# GAME's own composer (WO-P4-052, ``cockpit.viewport.compose_viewport_lines``)
# has no honest-empty TEXT of its own to reuse -- PWO-051 established the
# panel's honest-empty state as a truly BLANK interior (no placeholder, no
# marker glyph), unlike every panel above. A raising composer therefore
# falls back to the SAME blank state, not a fallback string -- an empty
# list draws nothing, exactly matching "no provider set" / "no event yet".
_VIEWPORT_COMPOSE_FAILED: list[str] = []
# The STOP banner's own composer (WO-P5-064, ``cockpit.stopbanner.
# compose_stop_banner_lines``) has no honest-empty state either -- an
# absent banner IS its calm state, and the banner only exists at all
# because a halt was reported. A raising composer therefore falls back to
# the bare attention glyph and nothing else: the operator still learns
# that SOMETHING halted the run (the one fact the region's presence
# already proves), and the reason slot stays empty rather than carrying
# invented text -- the same never-invent rule the composer itself is
# built around, applied to its own failure path.
_STOP_BANNER_COMPOSE_FAILED = ["!"]


def _validated_event_color_rows(event: object) -> list | None:
    """WO-P4-053: the RAW, untransformed ``event["color"]`` when it is
    genuinely usable for THIS SAME capture, else ``None``.

    Checked here -- one layer above
    ``cockpit.viewport_color.align_color_runs`` -- because that function
    has no way to detect a same-length-but-wrong-capture color map from
    inside itself (see its own CALLER CONTRACT section: a screen with a
    genuinely shorter/longer color map than its own ``screen`` would
    silently slice the WRONG rows against the surviving text, no crash, no
    empty result, every row's color just off by however many rows are
    missing). "Usable" means: ``event`` is a ``dict``, ``event["screen"]``
    and ``event["color"]`` are both ``list``/``tuple``, and their lengths
    match EXACTLY -- checked against the RAW ``screen`` here, before
    ``compose_viewport_lines``'s own top-drop/clip runs, since a
    legitimately-longer screen that top-drops down to the viewport's
    height is not a mismatch. Never raises; any shape that doesn't hold
    degrades to ``None`` (uncolored, never a guess) -- same
    honesty-over-plausible-guess convention as every other panel here."""
    if not isinstance(event, dict):
        return None
    raw_screen = event.get("screen")
    raw_color = event.get("color")
    if not isinstance(raw_screen, (list, tuple)) or not isinstance(raw_color, (list, tuple)):
        return None
    if len(raw_color) != len(raw_screen):
        return None
    return raw_color


def _resolve_last_rx_age_s(status: dict) -> float:
    """``status["idle_ms"]`` (the real wire field,
    ``tw2002_aiclient/session/protocol.py``'s ``status`` verb --
    ``resp["idle_ms"] = int((time.monotonic() - session.last_rx) * 1000)``)
    -> the ``last_rx_age_s`` seconds argument ``cockpit.tones.
    status_semantic`` expects. Defensive, never raises: a missing/
    non-numeric/non-finite/negative ``idle_ms`` all resolve to ``0.0``
    (freshest-possible, never fabricated staleness) -- this mirrors
    ``cockpit.tones``'s own ``_safe_rx_age`` policy of treating an unknown
    age as "we don't know how old this is", not "confidently very stale".
    Only reached once the caller has already confirmed a real, definite
    ``connected`` bool is present (see ``PlayShellScreen.
    _viewport_border_attr``'s honest-unknown gate) -- a missing/invalid
    ``idle_ms`` on an otherwise-real status payload still degrades to
    ``0.0`` rather than blocking the whole classification, since
    ``status_semantic`` only escalates past "ok" on staleness while
    ``connected`` is already ``True``."""
    idle_ms = status.get("idle_ms")
    try:
        idle_ms = float(idle_ms)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(idle_ms) or idle_ms < 0:
        return 0.0
    return idle_ms / 1000.0


BOUNDARY_LINE_1 = (
    "Rotation multiplies YOUR own daily turns across INDEPENDENT characters."
)
BOUNDARY_LINE_2 = (
    "Hard line: never transfer credits/cargo/assets between them."
)

# Ctrl-A (ASCII 1) -- the Mode chord (ADR-002, Accepted 2026-07-25,
# `canon/ADR/002-mode-chord-ctrl-a.md`; implemented here per WO-P5-061-
# ENTRY), replacing `M`/`m`. `handle_key` is only ever reached for this
# key while NOT attached (`app.py::_run_play` intercepts Ctrl-A itself,
# earlier, whenever it IS attached -- that module imports `MODE_KEY` from
# HERE rather than defining its own, so the two call sites can never
# silently drift apart onto different keycodes), so returning
# ``"attach"`` here unconditionally covers both legs of the toggle:
# Spectate->Human and App-hold->Human. No printable key may ever be Mode
# -- bare `M` is TradeWars' own Move command and must reach the game
# untouched once attached. THIS is the single source of truth for the
# keycode -- no leading underscore, since it is deliberately consumed
# cross-module (unlike this file's other `_`-private constants).
MODE_KEY = 1

# WO-PLAY-STRIP-TRAINER-CHROME: the CONN chip's own "slowly flashing"
# period (DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 3
# says "green slowly flashing", not a fixed literal duration). Chosen
# distinctly SLOWER than the heartbeat glyph's own
# `cockpit.liveness.HEARTBEAT_PERIOD_S = 0.8`, so the cockpit's two
# independent "is it alive" cues read as visually distinct pulses rather
# than the same blink repeated twice a few columns apart.
_CONN_FLASH_PERIOD_S = 1.6

# Connected-state glyph beside the host (hub REVISE chrome for
# WO-PLAY-STRIP-POLICY-AUTO): filled heartbeat-class dot, not the word
# CONN. Same codepoint as the bottom liveness heartbeat's lit phase
# (WO-CONN-HEARTBEAT-GLYPH) — intentional; distinguish by geometry
# (top strip vs control-strip), not whole-grid uniqueness. Private in
# liveness (`_HEARTBEAT_UNICODE[0]` / ASCII twin) so we keep local
# mirrors rather than importing private names.
_CONN_GLYPH_U = "●"  # ●
_CONN_GLYPH_A = "*"


def _conn_connected_tone(now: object) -> "str | None":
    """The CONN chip's tone while connected: alternates ``"ok"`` (lit
    green) / ``None`` (unlit) on ``_CONN_FLASH_PERIOD_S`` -- the identical
    ``int(now / period) % 2`` phase arithmetic
    ``cockpit.liveness.heartbeat_glyph`` uses for its own always-breathing
    cue, so this flash degrades exactly like every other time-driven
    signal in this cockpit: a hostile/non-finite/negative ``now`` collapses
    to phase 0 (lit) rather than raising or freezing dark. Never raises.
    """
    try:
        t = float(now)
    except Exception:
        t = 0.0
    if not math.isfinite(t):
        t = 0.0
    t = max(0.0, t)
    try:
        phase = int(t / _CONN_FLASH_PERIOD_S) % 2
    except Exception:
        phase = 0
    return "ok" if phase == 0 else None


class PlayShellScreen:
    """Trainer-cockpit frame bound to one launcher profile (WO-P1-016,
    PWO-031/033).

    Renders the two-weight bordered chrome from
    ``cockpit.layout.frame_layout``: a cyan-bold double-line outer frame
    titled ``PLAY SHELL``, the row-1 character/profile strip
    (``cockpit.strip.compose_profile_strip_segments_from_row`` --
    WO-PLAY-STRIP-TRAINER-CHROME moved the CONN chip onto this row beside
    the host, DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point
    3), a three-column body (left gutter: outer thin-rounded GOALS box with
    a nested thin-rounded FOCUS sub-box inside it, then a tall thin-rounded
    FORMATIONS box below spanning down toward LOGS (WO-LEFT-GUTTER-NEST-
    FOCUS-FORMATIONS, DECISION point 5) | double-line GAME viewport | right
    gutter stacked thin-rounded HUD above thin-rounded DECISIONS, PWO-036),
    and the bottom thin-rounded LOGS band carrying the daemon's advancing
    session transcript tail
    (WO-P3-041, ``cockpit.logsband.compose_logs_lines``, falling back to
    the ensure-session ``status_line`` only while no real tail exists yet;
    once a real tail exists, ``status_line`` still surfaces -- routed onto
    LOGS' own reserved bottom row rather than a mid-control-strip segment,
    WO-PLAY-STRIP-TRAINER-CHROME / DECISION point 4 -- see the LOGS
    paragraph below). The GAME viewport paints the live daemon screen
    (WO-P4-052, ``cockpit.viewport.compose_viewport_lines``, fed by
    ``viewport_provider``'s ``WatchFeed`` settle-edge snapshot) inside its
    zero-inset double-line border; with no provider set, no event yet, or a
    raising composer, the interior stays the honest blank 80x25 grid PWO-051
    shipped -- never placeholder text or fake content.
    Below the fold floor (``mode == "too_small"``) only the layout's
    refusal message is drawn. The left-gutter FORMATIONS box is the
    ``left_gutter`` region internally (WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS
    retargeted this region key from FOCUS -- its pre-this-WO occupant -- to
    FORMATIONS; ``cockpit.layout``'s PRIORITIES_W/PRIORITIES_MIN_W geometry
    constants are untouched). FOCUS's own box is computed on the fly from
    ``goals`` via ``cockpit.layout.nested_focus_region`` -- it has no
    top-level region key of its own, since it lives entirely inside
    ``goals``'s bounds. The right-gutter HUD box is likewise still the
    ``right_gutter`` region internally (unchanged key, pre-dating the
    split); DECISIONS is the new ``decisions`` region below it.

    The STOP banner (WO-P5-064, ``cockpit.stopbanner.
    compose_stop_banner_lines``) is the frame's one CONDITIONAL region: an
    unboxed warn-bold band between LOGS and the control strip, drawn only
    while the shared ``status`` snapshot reports a raised escalation
    (``intervention.needs_attention``), and absent entirely otherwise --
    "calm until it needs you". Its three bands name why the taught
    autopilot halted (a TYPED reason code resolved through the canon
    catalog, never invented prose), who the wire says holds the keyboard,
    and the A/R/T teach moves available at the halt (labels only -- their
    wires are PWO-066+). Because its presence depends on live daemon state
    rather than terminal size alone, ``draw()`` resolves the frame in two
    passes: a size-only probe to decide whether any status consumer exists
    this tier, the single ``status_provider()`` poll, then the final
    ``frame_layout(..., needs_attention=...)`` -- see ``draw()``'s own
    poll-guard comment.

    Responsive fold (WO-P3-039, canon `trainer-cockpit.md` "Responsive
    fold"): below ``layout.LEFT_GUTTER_MIN_COLS`` (138) the left gutter is
    absent entirely (``regions["goals"] is None``) while the DECISIONS host
    still survives -- GOALS, FOCUS, and FORMATIONS (WO-LEFT-GUTTER-NEST-
    FOCUS-FORMATIONS added the third) relocate INTO the idle DECISIONS pane
    rather than disappearing, via ``cockpit.fold.
    compose_folded_decisions_lines`` in place of ``cockpit.decisions.
    compose_decisions_lines`` for that one draw call. The DECISIONS box
    title stays ``"DECISIONS"`` either way; only its content composer
    switches, gated on ``goals is None`` (the exact fold-active condition --
    see the DECISIONS draw call below). At >=138 cols nothing changes; below
    ``RIGHT_GUTTER_MIN_COLS`` (118) ``decisions`` itself drops to ``None``
    first, so there is no host left to fold into.

    ``status_provider`` (PWO-034/035/036/037, WO-P3-038) is the shared data
    seam for every panel that reads live daemon state -- GOALS, nested
    FOCUS, and FORMATIONS in the left gutter, HUD and DECISIONS in the
    right, and now the
    ``control_strip`` liveness cluster (``cockpit.liveness.
    compose_liveness_cluster``) at the bottom: a no-arg callable returning a
    ``status`` dict (the daemon ``status`` verb shape) or ``None``.
    Defaults to ``None`` -- with no provider set, ``cockpit.goals.
    compose_goals_lines`` renders every row honestly unknown,
    ``cockpit.focus.compose_focus_lines`` renders its own honest-empty,
    ``cockpit.formations.compose_formations_panel`` renders its own
    honest-empty, ``cockpit.decisions.compose_decisions_lines`` renders its
    own ``["—", "Exploring…"]`` honest-empty, ``cockpit.hud.
    compose_hud_cells`` renders every cell sticky ``"-"`` with no freshness
    stamp, and ``compose_liveness_cluster`` renders its own idle ``→ -`` TX
    read, rather than any panel going blank or inventing content. Every
    panel reads the SAME single ``status_provider()`` snapshot per draw --
    one poll per tick, polled whenever ANY status-consuming region is
    present this tier (``goals``, ``decisions``, ``right_gutter``/HUD, OR
    ``control_strip`` -- never tied to any single one of them alone, so a
    fold that drops some of the four can never silently starve whichever
    one survives). ``app.py`` is the one place that assigns a real
    provider; a raising provider never crashes the draw pass (``draw()``
    catches around the call and falls back to ``None``, same
    honesty-over-crash convention as ``adapters.ensure_session``). HUD's
    own freshness dimming (``curses.A_DIM`` on stale value rows only, per
    ``cockpit.hud.FRESHNESS_STALE_S``) is drawn through
    ``cockpit_draw.draw_lines_attrs`` -- the per-line-attr sibling of
    ``draw_lines`` -- rather than ``draw_lines`` itself, since HUD is the
    one panel where some lines in the same box need a different attr than
    others (every other panel here still uses ``draw_lines``'s single flat
    attr).

    ``now_fn`` (WO-P3-038, extended by WO-P3-041) is a clock seam shared by
    the ``control_strip`` liveness cluster AND the LOGS newest-row flash
    below -- a no-arg callable returning a ``time.monotonic()``-shaped
    float, resolved ONCE per ``draw()`` call (not construction time) to the
    real ``time.monotonic`` when unset, and reused for both consumers
    rather than queried twice. Tests inject a scripted clock so the
    heartbeat phase (and, per this WO, the flash decision) is
    deterministic; the real refresh cadence (``app.py``'s 1 Hz
    ``stdscr.timeout(1000)``) is unchanged by this seam.

    LOGS (WO-P3-041, ``cockpit.logsband``; routing revised by
    WO-PLAY-STRIP-TRAINER-CHROME / DECISION
    `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 4): the SAME shared
    ``status`` snapshot's ``log_tail`` field composes the box's advancing
    transcript (``compose_logs_lines``, newest-last, clipped to the box's
    content rows). While ``cockpit_logsband.newest_tail_entry(status)`` is
    ``None`` -- no real daemon tail yet -- the box falls back to
    ``self.status_line`` (the local ensure-session progress/error string
    app.py sets) rather than the composer's own generic honest-empty
    marker, so the pre-tail ensure-session feedback (notably a failure
    reason) is never silently lost. Once a real tail exists AND
    ``status_line`` is non-empty, the two no longer compete for the same
    space: the transcript composer is asked for one row less and
    ``status_line`` takes the row it gave up, appended as the box's own
    last line -- "route status_line into LOGS ... without wiping the
    transcript" (DECISION point 4; this superseded WO-PLAY-OFFER-
    VISIBLE-ON-LIVE's mid-control-strip ``status_offer`` segment, which no
    longer exists). The newest row renders ``curses.A_BOLD`` for
    ``cockpit_logsband.TICKER_FLASH_DURATION_S`` (1.0s, canon's LOGS/ticker
    flash duration -- distinct from the CREDITS delta-chip's own 1.5s) after
    a genuinely NEW newest entry is observed -- tracked as this instance's
    own content-identity state (``_logs_last_newest`` /
    ``_logs_newest_arrival_s``), since ``cockpit_logsband`` is a pure,
    stateless composer with no draw-to-draw memory of its own. The flash
    always targets the newest TRANSCRIPT row, never the appended
    ``status_line`` row (which never flashes -- it is not real tail
    content).

    Every box border/title here renders in the ``"info"`` chrome tone
    (cyan, non-bold) sourced from ``cockpit.tones.SEMANTIC_COLORS`` -- the
    single source of truth (WO-P3-040) -- except the outer frame's own
    bold exception and the GAME viewport border's own STATE flip: cyan
    chrome by default, red non-bold the instant the same shared ``status``
    snapshot carries a real, definite ``connected: False`` (see
    ``_viewport_border_attr``). No gauge surface renders here
    (``gauge_semantic`` ships classifier-only, with no wired consumer yet).
    The App/Human mode badge *does* render on the control strip via
    ``cockpit.control_seat`` (WO-P5-060 LIVE) -- see the paragraphs below;
    an older revision of this docstring falsely claimed there was no badge.

    ``spectating``/``attached`` (PWO-055/WO-P5-060, ``cockpit.
    control_seat``) are this instance's own control-seat state. At entry
    BOTH are ``False`` -- App-hold, the chip reading ``APP`` -- because
    that is what the daemon itself is holding at that same instant:
    ``session/control_lock.py:59`` constructs ``self._mode = MODE_APP``,
    and nothing has called ``take_human()`` on a screen the human has not
    yet pressed Ctrl-A on. Canon says the same thing prescriptively --
    ``canon/surfaces/mode-line-and-teach-controls.md §"The mode line is a DUAL, not a triad"``, "Default when
    the client runs = App/autopilot", ratified in ADR-002 -- so
    WO-ENTRY-APP-CHIP is a code-to-canon correction: the prior
    ``spectating = True`` entry default made the cockpit open by asserting
    a state neither the daemon nor canon was in. Spectate survives as
    post-detach observation chrome, NOT as a Mode (ADR-002: "observation
    chrome only -- not a third dual position") -- ``app.py::_run_play``'s
    Ctrl-] branch and its broken-wire fallback set ``spectating = True``,
    and that is the only way this screen reaches the ``SPECTATE`` chip
    at all. This screen still has
    no send path of its own in ANY of these states (no `do`/`send`/
    `send_raw` verb reaches the daemon from here; the only wire traffic
    is the read-only ``status_provider`` poll and ``viewport_provider``'s
    subscribe feed -- ``tests/test_spectate_no_send.py``'s structural
    guards).

    The control-strip row's left side, which this docstring's own prior
    revision left blank pending N5, carries the honest mode chip --
    ``cockpit.control_seat``'s ``APP_LABEL``/``MANUAL_LABEL``/
    ``SPECTATE_LABEL`` reading, remapped via ``trainer_labels=True``
    (WO-PLAY-STRIP-TRAINER-CHROME) to the merged Mode-key+seat wording
    ``^A)APP-ARMED``/``^A)MANUAL-HUMAN`` (narrowing to ``^A)APP``/
    ``^A)MANUAL`` under width pressure; SPECTATE is deliberately NOT
    remapped -- DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`
    point 1: "keep honest SPECTATE ... do not lie APP-ARMED") -- right up
    against wherever the liveness cluster's own space begins, dropping out
    first if the row is too narrow for both (see
    ``compose_control_strip_segments``). This row no longer carries a
    separate ARM chip or the CONN chip (both retired from here by the same
    WO -- ARM is folded into the merged label above, CONN moved to the
    row-1 profile strip). The Mode chord (``handle_key``'s own
    ``"attach"`` return value, acted on by ``app.py::_run_play``) is
    **Ctrl-A**, not `M` -- WO-P5-061-ENTRY (project owner ruling,
    2026-07-25) moved it off `M` so bare `M` stays TradeWars' own Move
    command, unintercepted, while attached.

    Esc ends the binding and returns to the launcher — clean close, not a suspend.
    """

    # WO-P5-063: the pending confirm-to-arm gate, as ``(action, cycles)`` --
    # ``None`` when no gate is up. Set ONLY through ``begin_arm_confirm``.
    #
    # Declared at CLASS level, not only in ``__init__``, for two reasons that
    # point the same way:
    #
    # 1. **Safety direction.** ``None`` means "no gate is up", which is the
    #    state in which `y` does nothing. Making it the class default means
    #    EVERY instance -- however constructed -- starts unable to arm. There
    #    is no construction path, present or future, that can produce a
    #    cockpit one keystroke away from a live arm.
    # 2. **The suite's own construction idiom.** Several sibling suites build
    #    this screen with ``object.__new__(PlayShellScreen)`` to skip
    #    ``__init__`` and shim just the attributes under test (documented in
    #    ``tests/test_conn_toggle.py``). ``handle_key`` reads this attribute,
    #    so an ``__init__``-only assignment raises ``AttributeError`` on every
    #    such instance -- 20 pre-existing tests, none of them wrong. A class
    #    default keeps that idiom working instead of requiring every current
    #    and future shim-built test to know about this field.
    #
    # Deliberately NOT ``getattr(self, "_arm_confirm", None)`` at the read
    # site: that would paper over a genuinely missing attribute at the one
    # place where knowing the gate's real state matters, and it would put the
    # default somewhere a reader of the class body cannot see it.
    _arm_confirm: tuple[object, object] | None = None

    # WO-P5-070: pending analyze draft awaiting human y/N approval.
    _draft_approve: dict | None = None
    # WO-PLAY-RULE-IDENTITY: sequential typed entry for rule_id / do / priority.
    _rule_identity: dict | None = None

    # WO-PLAY-OFFER-VISIBLE-ON-LIVE: text that CLAIMS the hint band's slot.
    #
    # `None` -> the band shows the calm A/R/T teach tokens. A string -> that
    # string is shown instead. Canon sanctions exactly this: "When a taught
    # run is live, the band's slot is claimed instead by the AUTO-LOOP
    # cycle-progress bar ... never both, there is only room for one"
    # (`mode-line-and-teach-controls.md §"Spacing, alignment & hierarchy — the mode-line reading order"`).
    #
    # Why here and not the LOGS band, where the offer used to be written:
    # `status_line` only renders when LOGS has no real tail, so on a live
    # session the offer was written and never drawn (live prove,
    # `audit/live-play-ladder-newchar-9795263-20260727T0430Z.md`). Moving it
    # into the LOGS band was tried and measured: at the standard 40x160 frame
    # that band is `h=3`, i.e. ONE inner row, so giving the offer a row would
    # leave the transcript zero. The control strip is the surface canon
    # already assigns to affordance chrome, and it is visible on every frame
    # size the cockpit draws.
    explore_band: str | None = None
    # WO-WIRE-EXPLORE-DECISION-LINES: DECISIONS overlay lines while explore is
    # live. Set/cleared by app.py poll; draw injects onto the status snapshot.
    # Independent of explore_band (hint strip) — never steals cycle-progress.
    explore_decision_lines: list[str] | None = None

    def __init__(
        self,
        stdscr: curses.window,
        profile: ProfileRow,
        *,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self.stdscr = stdscr
        self.profile = profile
        self.status_line = ""  # set by app.py after the ensure_session() call
        self.status_provider: Callable[[], dict | None] | None = None  # set by app.py (PWO-034)
        # Producer for the GOALS Chain row's `chain_hops`/`chain_unit`, which
        # the daemon does not carry. Constructed HERE rather than by app.py so
        # the attribute always exists and is always usable: the chains-popup
        # branch calls `.update()` on it unconditionally, and a directly
        # constructed screen (as every pty test builds one) must not
        # AttributeError there.
        self.chain_scalars = _chain_status.ChainScalars()
        # Producer for the GOALS Map row's `known_sectors`, refreshed from the
        # chains-popup branch and explore terminal poll (see app.py); constructed
        # here for the same reason as `chain_scalars`.
        self.world_stats = _world_stats.WorldStats()
        # WO-PRIORITY-ENGINE-FOCUS-WIRE: FOCUS candidates overlay (display
        # only). Bound to chain_scalars so merge can see priced cycles.
        self.focus_scalars = _focus_status.FocusScalars(self.chain_scalars)
        # WO-P4-052: a no-arg callable returning a `WatchFeedSnapshot`-shaped
        # object (duck-typed via `.latest_event` only -- this module never
        # imports `WatchFeed` itself, see draw()'s own GAME viewport block).
        # Set by app.py to `feed.snapshot` (WO-P4-050's `WatchFeed`); `None`
        # here (the default) leaves the GAME interior blank, same as PWO-051.
        self.viewport_provider: Callable[[], object] | None = None
        # PWO-055 -- this cockpit instance's own relationship to the control
        # seat: is IT currently parked in read-only observation? Plain bool,
        # not a three-value mode string -- see ``cockpit.control_seat``'s
        # module docstring for why the pair is deliberately per-client
        # rather than mirroring the daemon's own wire-reported
        # app/human/spectate ``status["mode"]`` (a distinct, DAEMON-GLOBAL
        # fact).
        #
        # Defaults `False` (WO-ENTRY-APP-CHIP). This is a code-to-canon
        # correction, not a new product decision: canon already says
        # `mode-line-and-teach-controls.md §"The mode line is a DUAL, not a triad"` -- "Default when the client
        # runs = App/autopilot" -- ratified in ADR-002 (Accepted
        # 2026-07-25, `canon/ADR/002-mode-chord-ctrl-a.md §"Context"`: "Spectate is
        # not a Mode; default run = App/autopilot"). The code had drifted
        # from it. Together with `attached`'s own `False`
        # below this makes the entry state App-hold, whose chip reads
        # `APP` -- the honest mirror of `session/control_lock.py:59`'s
        # `self._mode = MODE_APP`, the seat the daemon genuinely holds
        # before any Ctrl-A. The prior `True` default published SPECTATE
        # at entry, a state the daemon was never in and which the ruling
        # has since removed from the Mode vocabulary entirely.
        #
        # Only `app.py::_run_play` ever sets this `True`: the Ctrl-] detach
        # branch and the broken-wire fallback, i.e. post-detach observation
        # chrome, explicitly preserved by the same ruling. Ctrl-A (canon
        # `mode-line-and-teach-controls.md §"The mode line is a DUAL, not a triad"`'s App<->Human
        # control-switch key -- moved off `M` by WO-P5-061-ENTRY) is what
        # takes/releases the daemon's Human lock; see ``handle_key``'s own
        # ``"attach"`` return value. This class itself still has no
        # send-capable call or symbol of its own in ANY of these states
        # (``tests/test_spectate_no_send.py``'s guards) -- it only ever
        # REPORTS the human's intent (``"attach"``) for ``app.py`` to act
        # on.
        self.spectating: bool = False
        # WO-P5-060 lane B: honest attach-state truth for the control-strip's
        # App/Human badge, mirroring `spectating`'s own plain-bool shape --
        # `app.py::_run_play` is the ONLY writer (attach success, the Ctrl-]
        # detach branch, the Ctrl-A App-hold release branch, and the
        # broken-wire fallback all set this alongside `spectating`, never
        # independently). Distinct from `not spectating`: this WO's own
        # call-site fix stops deriving `attached` from `spectating`'s
        # negation (PWO-056's interim shape) so the two diverge for the
        # real third App state (App-hold: both `False`, reachable via
        # Ctrl-A as of WO-P5-061-ENTRY) without a silent coupling bug.
        # Defaults `False` -- unchanged by WO-ENTRY-APP-CHIP, but now it
        # pairs with `spectating`'s own `False` above rather than its
        # former `True`, so the entry state IS that third App-hold case
        # (chip `APP`) instead of Spectate.
        self.attached: bool = False
        self._now_fn = now_fn  # WO-P3-038 -- resolved to time.monotonic at draw() time when unset
        # LOGS newest-row flash (WO-P3-041): content-identity tracking across
        # draw() calls -- cockpit.logsband is a pure, stateless composer (no
        # clock, no draw-to-draw memory), so this instance is the only place
        # "did a NEW line just arrive" can live. See draw()'s own LOGS block.
        self._logs_last_newest: str | None = None
        self._logs_newest_arrival_s: float | None = None
        self._outer_attr = curses.A_NORMAL
        self._chrome_attr = curses.A_NORMAL
        self._viewport_danger_attr = curses.A_NORMAL  # WO-P3-040 -- set for real below
        self._init_colors()
        # WO-PLAY-CONN-TOGGLE: keyboard focus for the CONN chip in the
        # control strip.  Arrow keys cycle focus; Enter activates (returns
        # "conn_activate" from handle_key).  False = no chip focused (the
        # default, unintrusive state).  Reset to False after activation in
        # app.py so the strip returns to its resting appearance.
        self._conn_focused: bool = False
        # WO-PLAY-STRIP-TRAINER-CHROME: the calm teachband's three
        # trainer-only toggles (DECISION
        # `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 2 -- "default
        # ON" for all three). `P`/`C`/`S` (see `handle_key` below) flip
        # these three booleans directly and return no intent -- this class
        # and `screens.py` never read them for anything but the calm
        # band's own `·ON`/`·OFF` rendering.
        #
        # WO-PLAY-STRIP-POLICY-AUTO landed the real daemon-side spend gate
        # this comment used to describe as a follow-on: `app.py`'s
        # `_autonomy_auto_fire` (an idle-tick function OUTSIDE this class,
        # reading these booleans through its `play` parameter) now honors
        # `port_trade_on`/`cargo_upgrade_on` for real -- App-armed +
        # ·ON reaches a live trade/hold-buy start with no human `y`. Still
        # true for `ship_upgrade_on` alone: no ship-upgrade engine or
        # `AutonomyOffer` kind exists yet, so it remains local-only chrome
        # by honest necessity, not by the same "not wired yet" reason the
        # other two used to share.
        self.port_trade_on: bool = True
        self.cargo_upgrade_on: bool = True
        self.ship_upgrade_on: bool = True
        # WO-EXPLORE-TRADE-MODE-SPLIT: L)ist-armed Trade Loop selection for T.
        # ``None`` = nothing armed. Dict shapes:
        #   {"kind": "discovered", "world_id": str, "fingerprint": str, "route": str}
        #   {"kind": "taught", "name": str}
        self.trade_loop_arm: dict | None = None
        # WO-P5-063: the pending confirm-to-arm gate. See the CLASS-level
        # default of the same name above for why it is declared there too;
        # this instance assignment is the ordinary path.
        self._arm_confirm: tuple[object, object] | None = None
        # WO-P5-068: the most-recently confirmed screen classification, set
        # by app.py after ensure_session() so Assign-Trigger (non-calm path)
        # can stamp the stub's ``when.screen`` field.  ``None`` before any
        # ensure result arrives (the honest "not yet known" state -- a
        # stub created before this is set will carry ``""`` via
        # ``cockpit.assign_trigger.create_stub``'s own degradation path).
        self.current_classification: str | None = None
        # WO-P5-068: in-memory stub store.  app.py calls
        # ``cockpit.assign_trigger.create_stub`` and stores the result
        # here on every "assign_trigger" action.  The store is test-
        # visible via ``play.stub_store.get()``.
        from tw2002_aiclient.cockpit import assign_trigger as _at
        self.stub_store = _at.StubStore()
        # WO-P5-067: in-cockpit record session.  Tracks the recording
        # lifecycle (start → add_step* → stop/cancel) for the R Record
        # teach key.  app.py toggles it on every "record_toggle" action.
        # The store is test-visible via ``play.record_session``.
        from tw2002_aiclient.cockpit import record_macro as _rm
        self.record_session = _rm.RecordSession()
        # WO-P5-069: in-cockpit Analyze overlay state.  Tracks whether
        # the Analyze overlay is open (``True``) or closed (``False``).
        # app.py opens/closes it on "analyze_open"/"analyze_close"
        # actions.  Never auto-opens; only an explicit A press (or the
        # corresponding close action) changes this state.
        # Test-visible via ``play.analyze_session``.
        self.analyze_session: cockpit_analyze.AnalyzeSession = (
            cockpit_analyze.AnalyzeSession()
        )
        # WO-PLAY-AUTOLOOP-START: canon's ``L)chains`` Trade-Loop-Chains
        # library popup.  Same overlay idiom as ``analyze_session`` above --
        # never auto-opens; only an explicit ``L`` (or a close action) moves
        # it.  app.py fills the rows from the loop store; this class holds
        # no store reader of its own.  Test-visible via ``play.chains_session``.
        self.chains_session: cockpit_chains.ChainsSession = (
            cockpit_chains.ChainsSession()
        )
        # WO-PLAY-RULES-LIBRARY: read-only blessed rules peek (U).
        self.rules_library_session: cockpit_rules_library.RulesLibrarySession = (
            cockpit_rules_library.RulesLibrarySession()
        )
        # WO-P5-070: in-flight analyze draft (pre-approval).  Cleared on
        # reject; promoted to ``stub_store`` only after ``draft_approve``.
        self.pending_analyze_draft: dict | None = None
        # WO-PLAY-RULE-IDENTITY: typed-entry session (None when idle).
        self._rule_identity: dict | None = None
        # Test-visible approval attribution (full LedgerWriter is deferred).
        self.approval_ledger_events: list[dict] = []

    def begin_draft_approve(self, draft: object = None) -> None:
        """Raise the analyze-draft approval gate (WO-P5-070). Never raises."""
        if isinstance(draft, dict):
            self._draft_approve = draft
        else:
            self._draft_approve = None

    def begin_rule_identity(self, stub: object = None) -> None:
        """Start Play typed-entry for rule_id / do / priority. Never raises."""
        self._rule_identity = cockpit_draft_approve.create_identity_session(stub)

    def _init_colors(self) -> None:
        # Tone-table fg names -- sourced from cockpit.tones via the
        # module-level _SEMANTIC_COLORS alias (WO-P3-040 single source of
        # truth), never a hardcoded curses.COLOR_* literal. The table's own
        # bold flags are deliberately NOT used below -- this class has its
        # own bold policy (outer frame bold, everything else non-bold,
        # including the viewport-border danger flip, which stays non-bold
        # even though the table's "danger" entry is bold=True elsewhere).
        info_fg_name, _unused_info_bold = _SEMANTIC_COLORS.get("info", ("cyan", False))
        danger_fg_name, _unused_danger_bold = _SEMANTIC_COLORS.get("danger", ("red", True))
        # The STOP banner is the one surface on this screen that IS bold by
        # canon rather than by this class's own policy: `mode-line-and-
        # teach-controls.md` "The STOP / escalation banner styling" paints
        # it "warn-tone (yellow) and BOLD ... an unmissable weight". Red is
        # deliberately NOT used (canon reserves it for hard link-down; an
        # autopilot halt is a screen it has not been taught yet, a warning,
        # not a failure), and neither is A_REVERSE (reserved as the one
        # selected/active/badge signal).
        warn_fg_name, _unused_warn_bold = _SEMANTIC_COLORS.get("warn", ("yellow", True))
        if not curses.has_colors():
            # Monochrome: bold marks the outer frame apart from the thin
            # instrument chrome, same as the launcher's monochrome fallback.
            # The viewport-border danger flip has no color to lean on here,
            # so it gets its own non-bold underline -- distinct from both the
            # bold-only outer frame and the plain chrome default, and never
            # A_REVERSE (reserved as the one selection/badge signal,
            # visual-language.md "load-bearing color rules").
            self._outer_attr = curses.A_BOLD
            self._chrome_attr = curses.A_NORMAL
            self._viewport_danger_attr = curses.A_UNDERLINE
            # No yellow to lean on here, so the honest remainder of
            # canon's "warn-tone AND bold" is the bold half alone -- which
            # still reads as weight against the plain chrome around it.
            # Deliberately NOT the underline the viewport-border flip
            # borrows in mono: that flip's own tone (danger) has no other
            # way to distinguish itself from the bold outer frame, whereas
            # bold alone already separates this banner from every
            # A_NORMAL panel row on the screen.
            self._stop_banner_attr = curses.A_BOLD
            return
        # Colors resolve through the ONE shared process-lifetime allocator
        # (WO-P3-040 REVISE, Mack CRITICAL) -- no init_pair call here
        # anymore. See _SharedPairs' own docstring for why a per-class
        # allocator corrupted other screens' already-cached colors (this
        # class's own former init_pair(1, ...)/init_pair(2, ...) calls were
        # the reproduced culprit -- they silently repainted the launcher's
        # already-cached pairs 1/2 the instant a PlayShellScreen was
        # constructed mid-session).
        # Cyan is chrome, never data (visual-language.md); the outer frame is
        # the one bold exception -- every other border/title stays non-bold
        # "info" tone so the eye lands on the game viewport, not the frame.
        self._chrome_attr = _shared_pairs.attr_for(info_fg_name)
        self._outer_attr = self._chrome_attr | curses.A_BOLD
        # The viewport border's own STATE flip (visual-language.md "the
        # viewport border is a STATE surface"): red, deliberately NON-bold
        # per canon's own wording -- distinct from both the bold-cyan outer
        # frame and the non-bold-cyan default chrome, never the tone table's
        # own (red, bold=True) "danger" attr.
        self._viewport_danger_attr = _shared_pairs.attr_for(danger_fg_name)
        if self._viewport_danger_attr == curses.A_NORMAL:
            # WO-P4-054 Gap 2, DOCS-WIN (canon `visual-language.md §"Three load-bearing color rules (apply on every surface, no exceptions)"`
            # "the viewport border is a STATE surface" -- "Mono /
            # color-unavailable interim: the same disconnect flip uses
            # A_UNDERLINE non-bold"). Canon scopes that interim to "color
            # unavailable" for the danger flip itself, not literally
            # `has_colors() == False` and not "danger happens to match
            # chrome" -- this branch is the code catching up to what canon
            # already prescribes for a route it had missed. Within this
            # branch `has_colors()` is already True (the mono path
            # returned above) and `danger_fg_name` always resolves to a
            # real color ("red", via cockpit.tones' own default), so
            # WO-P4-053's `_SharedPairs.attr_for` returning
            # `curses.A_NORMAL` here can ONLY mean the pair allocation
            # itself failed (process-lifetime pair-table exhaustion, or
            # any other curses.error on init_pair) -- `curses.color_pair(n)`
            # is never 0 for a real allocated n >= 1. Testing the danger
            # attr directly (rather than comparing it to `_chrome_attr`)
            # also covers the case where chrome's own earlier allocation
            # happened to succeed while danger's failed -- unreachable via
            # the real app's `_TonePalette()`-before-`PlayShellScreen`
            # construction order today (danger is always allocated before
            # chrome there, so a chrome-succeeds/danger-fails split can't
            # occur -- verified empirically), but this reads as the rule
            # canon actually states rather than a proxy for it, and stays
            # correct if that construction order ever changes. Left
            # unhandled, an allocation failure here would silently erase
            # the viewport border's disconnect signal (every existing test
            # asserts attr == self._viewport_danger_attr, so a collapse to
            # curses.A_NORMAL -- whatever chrome happened to get -- would
            # pass every one of them vacuously). Empirically reproduced
            # both ways: WO-P4-054's own
            # test_shared_pair_exhaustion_reproduces_and_is_fixed_by_underline_interim
            # (both colors exhaust together, the real-app-reachable case)
            # and test_danger_only_allocation_failure_still_gets_underline_interim
            # (chrome succeeds, danger alone fails -- construction-order
            # dependent, not reachable via `_run()` today, pinned as a
            # defensive rule-fidelity guard regardless).
            self._viewport_danger_attr = curses.A_UNDERLINE
        # Warn fg + bold, resolved through the ONE shared process-lifetime
        # pair allocator like every other colored attr on this screen. If
        # the allocation itself is unavailable (pair-table exhaustion),
        # `attr_for` returns A_NORMAL and the banner degrades to the same
        # bold-only weight the mono branch above uses -- honest without
        # color, never silently losing its "this is a halt" weight.
        self._stop_banner_attr = _shared_pairs.attr_for(warn_fg_name) | curses.A_BOLD

    def _viewport_border_attr(self, status: dict | None) -> int:
        """The GAME viewport border's own STATE flip (WO-P3-040, canon
        `visual-language.md` "the viewport border is a STATE surface"):
        cyan chrome by default, ``self._viewport_danger_attr`` (red,
        non-bold) the instant the real daemon status verb reports
        ``connected: False``.

        HONEST-UNKNOWN RULE: ``cockpit.tones.status_semantic`` is only ever
        called below with a genuinely real, definite ``connected`` bool read
        straight off the wire (``tw2002_aiclient/session/protocol.py``'s
        ``status`` dispatch -- ``resp["connected"] = session.conn.
        connected``, always a real bool on an ``ok`` response). A non-dict
        ``status`` (no provider set, or the provider returned/raised
        nothing usable -- see ``draw()``'s own guard around the
        ``status_provider()`` call), or a dict that lacks a real ``bool``
        ``connected`` field (a malformed/partial payload), both leave the
        border at its default chrome cyan -- this method never claims
        danger without real data, matching every other panel's own
        honest-unknown convention in this file.

        Only the ``"danger"`` tone flips the border; ``"warn"``/``"ok"``
        both render as the unchanged default chrome (canon's own wording
        describes a strict connected/disconnected flip, not a three-way
        gauge -- no gauge/badge surface is in scope for this WO)."""
        if not isinstance(status, dict):
            return self._chrome_attr
        connected = status.get("connected")
        if not isinstance(connected, bool):
            return self._chrome_attr
        last_rx_age_s = _resolve_last_rx_age_s(status)
        tone = cockpit_tones.status_semantic(connected, last_rx_age_s)
        if tone == "danger":
            return self._viewport_danger_attr
        return self._chrome_attr

    def _control_strip_segment_attr(self, tone: object) -> int:
        """Resolve one ``compose_control_strip_segments`` tone (``"ok"``,
        ``"warn"``, or ``None``) to a curses attr for a control-strip chip
        (WO-P5-060 the mode badge; WO-P5-062 the autopilot ARM chip routes
        through this same helper rather than growing a second attr path,
        so the two chips can never drift into different badge
        treatments). ``"ok"``/``"warn"`` resolve their
        SEMANTIC_COLORS fg (green/yellow, ``_SEMANTIC_COLORS`` sourced from
        ``cockpit.tones``, the single source of truth) through the ONE
        shared process-lifetime pair allocator (``_shared_pairs`` -- see its
        own class docstring for why a second allocator would corrupt other
        screens' already-cached colors), with ``curses.A_BOLD |
        curses.A_REVERSE`` layered on top -- canon's badge law
        (``mode-line-and-teach-controls.md §"Color semantics — the mode indicator, teach overlay, and the one 7-tone table"``: reverse-video is the
        one "selected/active/badge" signal) applied to BOTH dual chips (App
        AND Human), not just the newly-added App side, so the pair's visual
        register stays matched rather than splitting App-reversed/
        MANUAL-flat. Any other tone stays plain ``curses.A_NORMAL``,
        unreversed. Three things reach this helper carrying ``None``
        today: the SPECTATE chip (canon: deliberately uncolored), a
        PROVEN-disarmed ARM chip (WO-P5-062 -- same "nothing to see here"
        register, and the only arm reading that earns it), and every
        non-label segment such as the liveness cluster and the inter-chip
        separator.

        Mono/pair-exhaustion degrade (WO-P4-054 interim family): when the
        color allocation itself is unavailable (``_shared_pairs.attr_for``
        returns bare ``curses.A_NORMAL`` -- no color support, or the
        process-lifetime pair table is exhausted), the chip still carries
        ``A_BOLD | A_REVERSE`` on top of that ``A_NORMAL`` base -- an
        attribute-only badge, honest without color, rather than silently
        losing its "this is a chip" signal entirely. Never raises: an
        unrecognized/hostile ``tone`` degrades to the same plain
        ``A_NORMAL`` as ``None``."""
        if tone == cockpit_teachband.TEACH_TONE:
            # WO-P5-066: the standing teach band is canon's cyan chrome
            # accent -- "affordance chrome, not data"
            # (`mode-line-and-teach-controls.md §"Spacing, alignment & hierarchy — the mode-line reading order"`) -- so it takes
            # the SAME `_chrome_attr` the rest of the frame's chrome wears
            # and deliberately skips the `A_BOLD | A_REVERSE` badge below.
            # Reverse-video is canon's one "selected/active" signal
            # (`:179-181`); a hint band is neither selected nor active, and
            # badging it would make three unwired labels shout louder than
            # the ARM chip's real state.
            return self._chrome_attr
        if tone not in ("ok", "warn", "danger"):
            # Any other tone (None, SPECTATE's muted, separators, liveness)
            # stays plain A_NORMAL — unreversed, no badge treatment.
            return curses.A_NORMAL
        fg_name, _unused_bold = _SEMANTIC_COLORS.get(tone, ("default", False))
        base = _shared_pairs.attr_for(fg_name)
        return base | curses.A_BOLD | curses.A_REVERSE

    def begin_arm_confirm(self, action: object = None, *, cycles: object = None) -> None:
        """Raise the confirm-to-arm gate (WO-P5-063).

        The **single seam** through which a gate can appear. Nothing in the
        product calls it today: what canon says should raise it -- a
        Trade-Loop chain launch, a taught-run launch -- is the N5
        operate-the-app cluster (WO-071), unbuilt. A pinned test asserts
        there is still no production call site, so the day an arm path
        appears without its own WO it goes red first (Accept #5, "no silent
        arm inject in any code path").

        Raising the gate arms **nothing**. It only causes the prompt to be
        drawn and the next keystroke to be routed to
        ``armconfirm.resolve_arm_confirm_key``; only a subsequent `y`
        produces the ``"arm_confirm"`` intent, and even that intent has no
        daemon call behind it in this WO.
        """
        self._arm_confirm = (action, cycles)

    def _arm_confirm_attr(self) -> int:
        """The confirm gate's attr: table-row ``danger`` (red **BOLD**) plus
        ``A_REVERSE`` -- canon's "loudest combination the palette owns"
        (`visual-language.md §"Three load-bearing color rules (apply on every surface, no exceptions)"`).

        Routed through ``_control_strip_segment_attr`` rather than composing
        the attr here, so this gate and the chips beside it can never drift
        onto different treatments of the same tone name -- the same reason
        WO-P5-062's ARM chip was made to share that helper instead of
        growing a second attr path.

        **Deliberately NOT ``self._viewport_danger_attr``.** That attribute
        is the *other* ``danger``: `visual-language.md §"Three load-bearing color rules (apply on every surface, no exceptions)"` specifies red
        **non-bold** as a per-surface override for the viewport border's
        link-down flip, and this module's own comment at the point of
        divergence records it. It is on this class, it has ``danger`` in its
        name, and using it here would render the money-path gate *quieter*
        than the frame around it while still satisfying any check that only
        asked "is it danger-toned?". `visual-language.md §"Color semantics — the one 7-tone table"` lists "the
        live-play `y/N` confirm" among the **table row's** own examples.
        Pinned by attr identity, not by tone name.
        """
        return self._control_strip_segment_attr(cockpit_armconfirm.ARM_CONFIRM_TONE)

    def _compose_conn_chip(
        self,
        status: "dict | None",
        focused: bool,
        *,
        now: object = None,
        unicode_ok: object = True,
    ) -> "tuple[str, str | None]":
        """WO-PLAY-CONN-TOGGLE: compose the ``(text, tone)`` pair for the
        CONN chip (WO-PLAY-STRIP-TRAINER-CHROME moved this chip onto the
        top profile strip).

        Reads ``status["connected"]`` (the real bool the daemon reports on
        the ``status`` verb -- ``session.conn.connected``).  Three outcomes:

        * ``True``  → filled glyph ``●`` (ASCII ``*`` when ``unicode_ok``
          is falsey), or ``[●]`` / ``[*]`` when focused (brackets = focus
          cursor). ``tone`` is ``"ok"`` when ``now`` is omitted (every
          pre-trainer caller), or the SLOWLY FLASHING ``"ok"``/``None``
          alternation `_conn_connected_tone` computes from ``now`` when
          supplied -- DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`
          point 3: "green slowly flashing" when connected. This is
          strictly additive: omitting ``now`` reproduces steady-``"ok"``.
        * ``False`` → ``("DISC", "danger")`` red, or ``("[DISC]", "danger")``
          when focused. Never flashes -- DECISION: "offline/unknown =
          honest non-green (no lying pulse)".
        * Unknown (non-dict status, missing/non-bool field) →
          ``("DISC?", "warn")`` / ``("[DISC?]", "warn")`` — unknown state
          treated as "attention needed" per the established honest-unknown
          convention, NOT as "connected". Never flashes, same reason as
          ``False`` above.

        Tone matches the viewport border flip (``_viewport_border_attr``):
        ``"ok"`` / ``"danger"`` / ``"warn"`` -- draw layer resolves to
        green/red/yellow through ``_control_strip_segment_attr``, which was
        extended in this same WO to accept ``"danger"`` alongside ``"ok"``
        and ``"warn"``.  Never raises regardless of ``status``'s shape.
        """
        if isinstance(status, dict):
            connected = status.get("connected")
        else:
            connected = None
        if connected is True:
            tone = "ok" if now is None else _conn_connected_tone(now)
            try:
                use_u = bool(unicode_ok)
            except Exception:
                use_u = True
            glyph = _CONN_GLYPH_U if use_u else _CONN_GLYPH_A
            return (f"[{glyph}]" if focused else glyph, tone)
        if connected is False:
            return ("[DISC]" if focused else "DISC", "danger")
        # Unknown / no provider / provider raised
        return ("[DISC?]" if focused else "DISC?", "warn")

    def draw(self) -> None:
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        regions = frame_layout(max_y, max_x)
        if regions["mode"] == "too_small":
            cockpit_draw.draw_refuse_message(self.stdscr, regions["message"], self._outer_attr)
            self.stdscr.refresh()
            return

        # One status_provider() snapshot per draw, shared by every panel
        # that reads it -- GOALS/FOCUS in the left gutter, HUD/DECISIONS in
        # the right. Polled whenever ANY of `goals`, `decisions`, OR
        # `right_gutter` (HUD) is present this tier -- they fold
        # independently (`goals` gates on the left gutter's own pri_w > 0
        # check, `decisions` on the right gutter's own height contention
        # against HUD_BOX_MIN_H, `right_gutter` on has_right_gutter alone),
        # so the poll must never stay tied to any single one of them.
        # `right_gutter` was added here (PWO-037) as the same class of gap
        # that starved DECISIONS pre-036: layout.py's own stacked-gutter
        # comment documents DECISIONS shrinking then dropping (`None`) once
        # HUD alone consumes the right gutter's slot, which would leave
        # `right_gutter` as the tier's ONLY live status consumer with
        # `decisions` `None`. When PWO-037 added this term it was
        # DEFENSIVE: a `frame_layout` probe across every reachable
        # `(lines, cols)` found no tier where `decisions` actually
        # dropped while `right_gutter` survived (`column_h` never fell
        # below 14 at the MIN_LINES=20 floor, 2 rows clear of
        # HUD_BOX_MIN_H=12).
        #
        # WO-P5-064 made it LIVE. At a halt the INTERVENTION banner takes
        # up to 3 rows out of the column band before the gutters are
        # sized, so at 20..22 lines `column_h` falls to 10..12, `hud_h`
        # consumes the whole right-gutter slot, and `decisions` really is
        # `None` with `right_gutter` present -- exactly the state this
        # term was written for, now reachable rather than hypothetical.
        # (Probed directly across `lines` 20..44 at 160 cols: calm never
        # produces it at any size; a halt produces it at 20, 21, and 22.)
        # The guard needed no change -- it was already correct -- but it
        # is no longer a latent one, and never a second
        # `status_provider()` call per panel either way.
        #
        # `control_strip` was added here (WO-P3-038) as a FOURTH consumer
        # class -- and unlike `right_gutter` above, this one is LIVE, not
        # defensive: `control_strip` is present at every reachable
        # non-`too_small` tier today (layout.py's own CONTROL_STRIP_H
        # comment), INCLUDING the `minimal` tier (82..117 inner cols) where
        # `goals`/`decisions`/`right_gutter` are ALL `None` together (no
        # side gutters at all). Before this term, that tier polled zero
        # times per tick (see the now-updated
        # `tests/test_cockpit_hud_pty.py::
        # test_poll_guard_zero_calls_at_minimal_tier_with_no_status_consumer`,
        # which the WO-P3-038 dispatch flags as a disclosed 5th-file touch);
        # with `control_strip` present, that same real tier now needs
        # exactly one poll so the liveness cluster's `→ TX` read is live
        # rather than permanently idle-stub. Pinned by
        # `tests/test_cockpit_liveness_pty.py`'s own poll-guard test.
        #
        # Responsive fold (WO-P3-039) needs no FIFTH term here -- verified,
        # not assumed. The fold-active condition below (`goals is None`
        # while `decisions is not None`) is a strict subset of the existing
        # `decisions is not None` term: fold-active can only ever be true
        # when `decisions` is already present, so every fold-active tier
        # was already polling. No new gap, structurally -- not merely
        # unobserved at today's constants (unlike the `right_gutter` term
        # above, which IS a defensive/latent addition).
        #
        # The GAME viewport's own border-state flip (WO-P3-040,
        # `_viewport_border_attr` below) is a SIXTH consumer of this same
        # snapshot -- and, like the fold, needs no new term here either.
        # `layout.py`'s own CONTROL_STRIP comment establishes `control_strip`
        # is present at every reachable non-`too_small` size today,
        # independent of fold `mode` (explicitly including the `no_border`
        # tier where `center["border"]` is `False` and this new consumer
        # never even runs). So every tier where `center["border"]` could be
        # `True` already has `control_strip is not None` true and was
        # already polling -- structurally, not merely unobserved.
        #
        # LOGS (WO-P3-041, `cockpit.logsband.compose_logs_lines`) is a
        # SEVENTH consumer of this same snapshot -- and, like the fold and
        # the viewport-border flip above, needs no new term here either.
        # `logs` (unlike `right_gutter`/`decisions`/`goals`) has no `None`
        # branch of its own anywhere in `layout.py`'s non-`too_small` path
        # -- `logs_h_actual` is computed unconditionally and is always
        # >= 1 (LOGS claims its floor FIRST, before CONTROL_STRIP's own
        # carve). So `logs` is present at every reachable non-`too_small`
        # tier, the exact same footprint `control_strip` already has (see
        # `layout.py`'s own CONTROL_STRIP_H comment) -- `regions
        # ["control_strip"] is not None` in the guard below is therefore
        # already true at every tier where LOGS itself is drawn, and
        # LOGS's own status read (`status.get("log_tail")`,
        # `cockpit_logsband.newest_tail_entry`) shares this SAME polled
        # `status`, never a second `status_provider()` call.
        #
        # WO-P5-064 moved this poll UP, ahead of every draw call in this
        # method, and split the frame resolution into two passes. The
        # STOP banner's region is the first one whose PRESENCE depends on
        # live daemon state (`intervention.needs_attention`) rather than
        # on terminal size alone, and claiming its rows re-sizes the
        # column band every other panel measures itself against -- so the
        # geometry has to be final BEFORE the first box is drawn, and the
        # status it depends on has to be read before that. The two
        # `frame_layout` calls are both pure and cheap; the POLL is what
        # this guard protects, and there is still exactly ONE of those per
        # draw (pinned by `tests/test_cockpit_stopbanner_wiring.py::
        # test_exactly_one_status_poll_per_draw_halt_or_not`).
        #
        # The guard needs no new term for the banner itself -- verified,
        # not assumed: `control_strip` (already a term) is present at
        # every reachable non-`too_small` tier, per `layout.py`'s own
        # CONTROL_STRIP_H comment, so every tier that could raise a banner
        # was already polling. The probe pass reads regions from the CALM
        # layout, which is the correct side to guard on: a halt only ever
        # takes rows away, so a consumer present in the final layout is
        # always present in the probe too (never the reverse).
        if (
            regions["goals"] is not None
            or regions["decisions"] is not None
            or regions["right_gutter"] is not None
            or regions["control_strip"] is not None
        ):
            try:
                status = self.status_provider() if self.status_provider is not None else None
            except Exception:  # noqa: BLE001 -- a raising provider must not crash the draw pass
                status = None
            # WO-WIRE-EXPLORE-DECISION-LINES: overlay explore DECISIONS lines onto
            # the same status dict DECISIONS/fold already consume. Display-only;
            # does not steal explore_band / cycle-progress chrome.
            try:
                from tw2002_aiclient import explore as _explore_overlay

                status = _explore_overlay.merge_explore_decision_lines(
                    status, getattr(self, "explore_decision_lines", None)
                )
            except Exception:  # noqa: BLE001 -- overlay must not crash the draw pass
                pass
        else:
            status = None

        # The final frame. A raising `needs_attention` (a hostile status
        # payload reaching a shape the gate cannot read) degrades to the
        # calm layout rather than crashing the draw pass -- same
        # honesty-over-crash containment as every composer call below;
        # the cost of getting this wrong is a missing banner for one
        # tick, never a dead cockpit.
        try:
            halting = cockpit_stopbanner.needs_attention(status)
        except Exception:  # noqa: BLE001 -- a raising gate must not crash the draw pass
            halting = False
        if halting:
            regions = frame_layout(max_y, max_x, needs_attention=True)

        uok = cockpit_draw.unicode_ok()

        # `now_val` (WO-P3-038, extended WO-P3-041, hoisted earlier still by
        # WO-PLAY-STRIP-TRAINER-CHROME): resolved ONCE per draw, here rather
        # than down at the LOGS block, because the row-1 profile strip's own
        # CONN chip (DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`
        # point 3, moved from the control strip) now needs it too -- every
        # time-driven cue in this draw pass (this CONN flash, LOGS' own
        # newest-row flash, CONTROL_STRIP's heartbeat) shares the identical
        # reading rather than each querying the clock separately.
        try:
            now_val = (self._now_fn or time.monotonic)()
        except Exception:  # noqa: BLE001 -- a raising now_fn must not crash the draw pass
            # Fall back to the REAL clock, not a frozen 0.0: the
            # heartbeat's whole job is proving the draw loop is still
            # running (canon "always breathing... so 'alive' reads even
            # on a settled screen") -- the loop IS running (we got this
            # far), so the true signal should survive a broken injected
            # clock rather than lying still.
            now_val = time.monotonic()

        # Outer frame -- double-line, cyan+bold, titled on its own top-border
        # row (row 1 below it is fully claimed by the character/profile strip).
        cockpit_draw.draw_box(
            self.stdscr, regions["outer"], weight="double", attr=self._outer_attr,
            title=PLAY_TITLE.strip(), title_attr=self._outer_attr, uok=uok,
        )

        # Row-1 profile strip (WO-PLAY-STRIP-TRAINER-CHROME / DECISION point
        # 3): CONN now rides beside the host on THIS row instead of the
        # bottom control strip -- `status` is the same shared snapshot every
        # other panel in this draw already reads (no second poll), and
        # `now_val` (hoisted above) drives the chip's own slow green flash
        # while connected (`_compose_conn_chip`/`_conn_connected_tone`).
        # Segmented (`compose_profile_strip_segments_from_row` +
        # `draw_segment_line`) rather than the flat-string composer/
        # `draw_lines` pairing this row used pre-trainer, so the CONN chip
        # can carry its own tone distinct from the plain identity text
        # around it -- the identical segments-vs-flat-string split the
        # control strip already uses for its own mode-badge chip. A raising
        # composer degrades to an empty row rather than crashing the draw
        # pass, same containment discipline as every other composer call in
        # this method.
        strip_region = regions["strip"]
        try:
            conn_chip = self._compose_conn_chip(status, self._conn_focused, now=now_val, unicode_ok=uok)
        except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
            conn_chip = None
        try:
            strip_segments_raw = compose_profile_strip_segments_from_row(
                self.profile,
                width=strip_region["w"] if strip_region else 0,
                unicode_ok=uok,
                conn_chip=conn_chip,
            )
        except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
            strip_segments_raw = []
        # Strip content is profile identity -- DATA, not chrome. Canon
        # doctrine ("cyan is chrome, never data", visual-language.md) reads
        # as an interim ruling here pending hub ratification of this
        # concept's own promotion out of staged status; plain A_NORMAL
        # (default fg, non-bold) keeps the identity text un-tinted while the
        # outer frame's own border stays cyan around it -- only the CONN
        # chip segment itself carries a real tone attr, through the SAME
        # `_control_strip_segment_attr` helper the control strip below
        # already uses (a generic tone->attr resolver, not a control-strip-
        # only one, despite its name).
        strip_segments = [
            (str(text), self._control_strip_segment_attr(tone) if tone else curses.A_NORMAL)
            for text, tone in strip_segments_raw
        ]
        cockpit_draw.draw_segment_line(self.stdscr, strip_region, strip_segments, boxed=False)

        goals = regions["goals"]
        cockpit_draw.draw_box(
            self.stdscr, goals, weight="thin", attr=self._chrome_attr,
            title="GOALS", title_attr=self._chrome_attr, uok=uok,
        )
        decisions = regions["decisions"]
        if goals is not None:
            goals_inner_w = max(0, goals["w"] - 2)
            try:
                goals_lines = cockpit_goals.compose_goals_lines(status, width=goals_inner_w)
            except Exception:  # noqa: BLE001 -- operator keeps control over panel-render failures
                goals_lines = _GOALS_COMPOSE_FAILED
        else:
            goals_lines = []
        cockpit_draw.draw_lines(self.stdscr, goals, goals_lines, curses.A_NORMAL)

        # FOCUS nests INSIDE the GOALS box as of
        # WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS (box-in-box, not a sibling
        # stacked below it) -- `nested_focus_region` computes its own
        # top/bottom-bordered sub-rect entirely within `goals`'s bounds, so
        # drawing FOCUS's own box here paints strictly inside GOALS's
        # already-drawn border, never past it.
        focus = nested_focus_region(goals)
        cockpit_draw.draw_box(
            self.stdscr, focus, weight="thin", attr=self._chrome_attr,
            title="FOCUS", title_attr=self._chrome_attr, uok=uok,
        )
        if focus is not None:
            focus_inner_w = max(0, focus["w"] - 2)
            try:
                focus_lines = cockpit_focus.compose_focus_lines(status, width=focus_inner_w)
            except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                focus_lines = _FOCUS_COMPOSE_FAILED
        else:
            focus_lines = []
        cockpit_draw.draw_lines(self.stdscr, focus, focus_lines, curses.A_NORMAL)

        # FORMATIONS retargets the `left_gutter` region key -- FOCUS's own
        # slot pre-this-WO, now claimed by a genuinely tall panel that
        # extends the left column below GOALS down toward LOGS (WO scope
        # item 2/3). Honest-empty via `formations.compose_formations_panel`
        # until a later WO wires a real catalog (see that module's
        # docstring).
        left = regions["left_gutter"]
        cockpit_draw.draw_box(
            self.stdscr, left, weight="thin", attr=self._chrome_attr,
            title="FORMATIONS", title_attr=self._chrome_attr, uok=uok,
        )
        if left is not None:
            left_inner_w = max(0, left["w"] - 2)
            try:
                formations_lines = cockpit_formations.compose_formations_panel(
                    status, width=left_inner_w
                )
            except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                formations_lines = _FORMATIONS_COMPOSE_FAILED
        else:
            formations_lines = []
        cockpit_draw.draw_lines(self.stdscr, left, formations_lines, curses.A_NORMAL)

        # GAME viewport (PWO-051 shell, WO-P4-052 live paint). At the
        # `no_border` tier (`center["border"]` False) nothing is drawn at
        # all -- the region stays reserved by `frame_layout`, same "reserved
        # but unpainted" convention the tall-terminal gap band already uses
        # elsewhere in this frame. At the bordered tiers the double-line
        # frame + title always render; the interior paints the live daemon
        # screen when a real `viewport_provider` event is available, and
        # otherwise stays exactly the honest blank grid PWO-051 shipped (no
        # placeholder text, no fake data) -- see `_VIEWPORT_COMPOSE_FAILED`.
        center = regions["center"]
        if center is not None and center["border"]:
            # WO-P3-040: the viewport border's own STATE flip -- cyan
            # chrome by default, red non-bold the instant a real,
            # definite `connected: False` reaches us (honest-unknown
            # otherwise; see `_viewport_border_attr`'s own docstring).
            border_attr = self._viewport_border_attr(status)
            cockpit_draw.draw_box(
                self.stdscr, center, weight="double", attr=border_attr,
                title="GAME", title_attr=border_attr, uok=uok,
            )
            # One `viewport_provider()` poll per draw (mirrors
            # `status_provider`'s own one-call-per-draw discipline) --
            # only ever reached here, inside the already-established
            # bordered-tier guard, so a `no_border` tier never polls at
            # all. `event` is duck-typed off the snapshot's `.latest_event`
            # attribute only -- this module never imports `WatchFeed` or
            # `WatchFeedSnapshot` -- and a raising provider (or a hostile
            # `.latest_event` property) degrades to `None`, never crashing
            # the draw pass, same honesty-over-crash convention as
            # `status_provider` above.
            event = None
            if self.viewport_provider is not None:
                try:
                    event = self.viewport_provider().latest_event
                except Exception:  # noqa: BLE001 -- a raising provider must not crash the draw pass
                    event = None
            center_inner_w = max(0, center["w"] - 2)
            center_inner_h = max(0, center["h"] - 2)
            try:
                viewport_lines = cockpit_viewport.compose_viewport_lines(
                    event, width=center_inner_w, height=center_inner_h
                )
            except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                viewport_lines = _VIEWPORT_COMPOSE_FAILED
            # WO-P4-053: per-cell TWGS color. `color_rows` is the RAW event
            # color map, validated ONE LAYER UP against the raw `screen`
            # (see `_validated_event_color_rows`'s own docstring for why
            # `align_color_runs` itself cannot make this call) -- a `None`
            # here (absent color, e.g. the one-shot `screen` raw path never
            # emits one, or a count mismatch) degrades every row to an
            # empty run list, i.e. uncolored text, never a raise, never a
            # guess.
            color_rows = _validated_event_color_rows(event)
            try:
                aligned_runs = cockpit_viewport_color.align_color_runs(color_rows, viewport_lines)
            except Exception:  # noqa: BLE001 -- a raising aligner must not crash the draw pass
                aligned_runs = [[] for _ in viewport_lines]
            # Resolve each aligned run's (fg, bg, bold) to a concrete curses
            # attr through the SAME `_shared_pairs` allocator every chrome
            # color already uses (WO-P4-053 draw-seam merge -- see
            # `_SharedPairs`' own docstring for why a second allocator here
            # would reopen the pair-number-collision bug it exists to
            # eliminate). `run_attr` never raises by its own contract; the
            # `try/except` below is the same defensive belt-and-suspenders
            # every other composer call in this method already wears.
            runs_lines: list[tuple[str, list[dict]]] = []
            for text, runs in zip(viewport_lines, aligned_runs):
                resolved_runs: list[dict] = []
                for run in runs:
                    try:
                        attr = cockpit_viewport_color.run_attr(_shared_pairs, run)
                    except Exception:  # noqa: BLE001 -- a raising resolver must not crash the draw pass
                        continue
                    resolved_runs.append({"start": run["start"], "end": run["end"], "attr": attr})
                runs_lines.append((text, resolved_runs))
            # Routes through `draw_runs` -- the per-run-attr choke point
            # `draw_lines`/`draw_lines_attrs` themselves don't cover --
            # which still shares their `cockpit.draw._safe_write`/
            # `_clip_cells` guard for both the uncolored base layer and
            # every color run overlaid on top, so hostile CSI/OSC bytes
            # surviving into a game-screen cell can never escape this box
            # the same way they can't escape any other panel's. A row whose
            # run list ends up empty (no color captured, or dropped by the
            # validation above) still paints its full text via `draw_runs`'
            # own uncolored base layer -- content is never lost to a color
            # failure.
            cockpit_draw.draw_runs(self.stdscr, center, runs_lines)

        # WO-PLAY-CHAIN-BUBBLE-VIZ: always-on best-chain bubbles under the
        # viewport. Reads the cached chain from `chain_scalars` only — never
        # calls chain_search / world_model / filesystem on the draw path.
        # Fold while L)chains is open so the modal's empty/unreadable wording
        # is not shadowed by the strip's quiet "no trade loop yet" placeholder
        # (same canon words; different facts).
        chain_region = regions.get("chain")
        _cs_open = getattr(getattr(self, "chains_session", None), "is_open", False)
        if chain_region is not None and not _cs_open:
            cur_sector = None
            try:
                hud = status.get("hud") if isinstance(status, dict) else None
                sector_cell = hud.get("sector") if isinstance(hud, dict) else None
                if isinstance(sector_cell, dict):
                    cur_sector = sector_cell.get("value")
                else:
                    cur_sector = sector_cell
            except Exception:  # noqa: BLE001
                cur_sector = None
            try:
                subject, caption = self.chain_scalars.bubble_subject(
                    current_sector=cur_sector,
                )
                bubble_lines = cockpit_chain_bubbles.compose_chain_bubbles(
                    subject,
                    current_sector=cur_sector,
                    port_classes=self.chain_scalars.port_classes,
                    known_ports=self.chain_scalars.known_ports or None,
                    width=chain_region["w"],
                    caption=caption,
                )
            except Exception:  # noqa: BLE001 -- never crash the draw pass
                bubble_lines = [""] * cockpit_chain_bubbles.CHAIN_VIZ_H
            cockpit_draw.draw_lines(
                self.stdscr, chain_region, bubble_lines, curses.A_NORMAL, boxed=False,
            )

        right = regions["right_gutter"]
        cockpit_draw.draw_box(
            self.stdscr, right, weight="thin", attr=self._chrome_attr,
            title="HUD", title_attr=self._chrome_attr, uok=uok,
        )
        if right is not None:
            hud_inner_w = max(0, right["w"] - 2)
            try:
                hud_cells = cockpit_hud.compose_hud_cells(
                    status, width=hud_inner_w, unicode_ok=uok
                )
            except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                hud_cells = _HUD_COMPOSE_FAILED
        else:
            hud_cells = []
        # HUD dims only STALE VALUE rows (content stays data-tone, never a
        # color swap -- "cyan is chrome, never data") -- the one panel
        # needing draw_lines_attrs' per-line attr rather than draw_lines'
        # single flat one.
        hud_lines_attrs = [
            (text, curses.A_DIM if stale else curses.A_NORMAL) for text, stale in hud_cells
        ]
        cockpit_draw.draw_lines_attrs(self.stdscr, right, hud_lines_attrs)

        cockpit_draw.draw_box(
            self.stdscr, decisions, weight="thin", attr=self._chrome_attr,
            title="DECISIONS", title_attr=self._chrome_attr, uok=uok,
        )
        if decisions is not None:
            decisions_inner_w = max(0, decisions["w"] - 2)
            # Responsive fold (WO-P3-039, canon `trainer-cockpit.md`
            # "Responsive fold"): below `LEFT_GUTTER_MIN_COLS` (138) the
            # left gutter is absent entirely (`goals is None`) while the
            # right gutter/DECISIONS host still survives -- GOALS+FOCUS+
            # FORMATIONS relocate INTO the idle DECISIONS pane rather than
            # disappearing. `goals is None` (checked here, inside the
            # already-established `decisions is not None` guard) is
            # therefore the exact fold-active condition: at >=138 `goals`
            # is present and this stays the unfolded path; below 118
            # `decisions` itself drops to `None` first (no host to fold
            # into -- nothing to wire, per canon's own ladder), so this
            # branch is only ever reached at a genuine narrow-right tier.
            if goals is None:
                try:
                    decisions_lines = cockpit_fold.compose_folded_decisions_lines(
                        status, width=decisions_inner_w
                    )
                except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                    decisions_lines = _FOLD_COMPOSE_FAILED
            else:
                try:
                    decisions_lines = cockpit_decisions.compose_decisions_lines(
                        status, width=decisions_inner_w
                    )
                except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
                    decisions_lines = _DECISIONS_COMPOSE_FAILED
        else:
            decisions_lines = []
        cockpit_draw.draw_lines(self.stdscr, decisions, decisions_lines, curses.A_NORMAL)

        # `now_val` (WO-P3-038, extended WO-P3-041) was hoisted up ahead of
        # the row-1 profile strip by WO-PLAY-STRIP-TRAINER-CHROME (see that
        # comment) -- LOGS' own newest-row flash and CONTROL_STRIP's
        # heartbeat below share that SAME reading, never a second clock
        # query.
        logs = regions["logs"]
        cockpit_draw.draw_box(
            self.stdscr, logs, weight="thin", attr=self._chrome_attr,
            title="LOGS", title_attr=self._chrome_attr, uok=uok,
        )
        logs_inner_w = max(0, logs["w"] - 2)
        logs_inner_h = max(0, logs["h"] - 2)
        try:
            current_newest = cockpit_logsband.newest_tail_entry(status)
        except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
            current_newest = None
        has_real_tail = current_newest is not None
        # WO-PLAY-STRIP-TRAINER-CHROME / DECISION
        # `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 4: `status_line`
        # now always routes into LOGS -- the control strip's own mid-strip
        # `status_offer` segment (WO-PLAY-OFFER-VISIBLE-ON-LIVE) is retired
        # below. While a REAL transcript exists, reserve its bottom-most row
        # for `status_line` rather than replacing the tail outright --
        # "don't wipe the transcript" (DECISION point 4): the composer is
        # asked for one row less so the appended status row never displaces
        # transcript content it already decided to show. While there is no
        # real tail yet, the pre-existing WO-P3-041 fallback below is
        # unchanged (the WHOLE box is the status line -- nothing to
        # preserve).
        status_text = self.status_line if isinstance(self.status_line, str) else ""
        reserve_status_row = bool(has_real_tail and status_text and logs_inner_h > 0)
        tail_h = max(0, logs_inner_h - 1) if reserve_status_row else logs_inner_h
        try:
            logs_lines = cockpit_logsband.compose_logs_lines(
                status, width=logs_inner_w, height=tail_h
            )
        except Exception:  # noqa: BLE001 -- a raising panel must not crash the draw pass
            logs_lines = _LOGS_COMPOSE_FAILED[:tail_h]
            has_real_tail = False  # a raising composer can't be trusted to carry real content
            reserve_status_row = False
        # `status_line` fallback (WO-P3-041): while there is no real daemon
        # tail (`has_real_tail` False -- honest-empty OR a raising
        # composer), surface app.py's own ensure-session progress/error
        # text instead of the composer's generic marker, so that feedback
        # (notably a failure reason) is never silently lost. Keyed off
        # `has_real_tail` (derived from `newest_tail_entry`, independent of
        # any width-driven truncation `compose_logs_lines` may have already
        # applied to its OWN honest-empty text) rather than a fragile
        # string comparison against the (possibly-clipped) composed line.
        if not has_real_tail and status_text and logs_inner_h > 0:
            logs_lines = [status_text[:logs_inner_w]] if logs_inner_w > 0 else [""]
        elif reserve_status_row:
            # A real tail AND a status line both want the box: the tail
            # keeps every row above the last (composed against `tail_h`
            # above, one row narrower than the box), and `status_line`
            # takes the row the tail gave up -- both visible, neither wiped.
            logs_lines = logs_lines + [status_text[:logs_inner_w]]

        # Newest-row flash (WO-P3-041, canon "the newest LOGS/ticker row
        # flashes on arrival"): content-identity tracking is THIS
        # instance's own state -- `cockpit_logsband` is a pure, stateless
        # composer with no draw-to-draw memory. A changed `current_newest`
        # (including a transition to/from `None`) is a fresh arrival;
        # an unchanged one leaves the prior arrival timestamp untouched.
        # Known limitation (accepted): a consecutive genuinely-new arrival
        # with IDENTICAL text to the tracked newest does not re-flash
        # (realistic under per-keystroke attach, repeated identical keys);
        # ring churn at TAIL_MAX makes length-based detection equally
        # blind. Canon's "just-arrived" wording doesn't promise per-
        # duplicate flashes. Fix: session-side arrival counter (follow-on).
        if current_newest != self._logs_last_newest:
            self._logs_last_newest = current_newest
            self._logs_newest_arrival_s = now_val if current_newest is not None else None
        try:
            logs_newest_flashing = cockpit_logsband.flash_active(
                self._logs_newest_arrival_s, now=now_val
            )
        except Exception:  # noqa: BLE001 -- a raising helper must not crash the draw pass
            logs_newest_flashing = False

        logs_attrs = [(line, curses.A_NORMAL) for line in logs_lines]
        if has_real_tail and logs_newest_flashing and logs_attrs:
            # Only the bottom (newest) TRANSCRIPT line ever flashes, and
            # only when it is genuine tail content -- the `status_line`
            # fallback line never flashes (it is not a transcript arrival).
            # When `reserve_status_row` appended `status_line` as this
            # list's own last entry (WO-PLAY-STRIP-TRAINER-CHROME), the
            # newest TRANSCRIPT row is the entry just above it instead. At
            # the real MIN_LINES floor (`logs_inner_h == 1`) the reserved
            # status row consumes the box's ONLY row, leaving no separate
            # transcript row to flash at all -- `flash_index=-1` would
            # otherwise wrongly bold `status_line` itself, so this case
            # flashes nothing rather than mislabel chrome as a fresh
            # transcript arrival.
            flash_index: int | None
            if reserve_status_row:
                flash_index = -2 if len(logs_attrs) >= 2 else None
            else:
                flash_index = -1
            if flash_index is not None:
                last_text, _ = logs_attrs[flash_index]
                logs_attrs[flash_index] = (last_text, curses.A_BOLD)
        cockpit_draw.draw_lines_attrs(self.stdscr, logs, logs_attrs)

        # INTERVENTION / STOP banner (WO-P5-064, canon
        # `mode-line-and-teach-controls.md` "The STOP banner" + "The STOP /
        # escalation banner styling"). Unboxed like the control strip and
        # the row-1 profile strip -- canon is explicit that this is "an
        # unboxed single row led by a bare `!`" (three rows in the reborn
        # three-band form), not a titled instrument box. Present only when
        # the same shared `status` snapshot reports a raised escalation,
        # so the calm cockpit shows no banner at all rather than a
        # reserved-but-empty band ("calm until it needs you").
        #
        # One flat warn+bold attr for all three rows, per canon's own
        # `_draw_intervention_strip` grounding ("the draw doubles A_BOLD
        # on top of the `warn` tone for an unmissable weight") -- so this
        # is a plain `draw_lines` call, not the per-line `draw_lines_attrs`
        # LOGS needs or the per-segment `draw_segment_line` the mode chip
        # needs. The GAME viewport's own cells are untouched by any of
        # this: the banner is chrome in its own region, never a re-tint of
        # the operator's actual screen.
        #
        # A raising composer degrades to `_STOP_BANNER_COMPOSE_FAILED`
        # (the bare `!`, no invented reason text) rather than crashing the
        # draw pass or silently swallowing the halt -- same containment
        # discipline as every other composer call in this method.
        intervention = regions["intervention"]
        if intervention is not None:
            try:
                banner_lines = cockpit_stopbanner.compose_stop_banner_lines(
                    status, width=intervention["w"], height=intervention["h"]
                )
            except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
                banner_lines = _STOP_BANNER_COMPOSE_FAILED[: intervention["h"]]
            cockpit_draw.draw_lines(
                self.stdscr, intervention, banner_lines, self._stop_banner_attr, boxed=False
            )

        # CONTROL_STRIP (WO-P3-038, PWO-055, PWO-056, WO-P5-060,
        # WO-ENTRY-APP-CHIP, WO-P5-062): the frame's own bottom-most
        # interior row, a bare content row (no box -- same `boxed=False`
        # shape as the row-1 profile strip). Carries three things: the
        # liveness cluster, right-aligned (unchanged); the honest mode
        # chip hard-left; and, immediately right of it, the autopilot ARM
        # chip (WO-P5-062, wired further down). The mode chip fills
        # whatever room remains -- `cockpit.control_seat.APP_LABEL`
        # while neither flag is set (WO-P5-060), which as of
        # WO-ENTRY-APP-CHIP is the ENTRY state itself, mirroring the
        # daemon's own standing `MODE_APP` default
        # (`session/control_lock.py:59`), and is also where Ctrl-A's
        # Human->App-hold leg lands (WO-P5-061-ENTRY); `MANUAL_LABEL`
        # ("MANUAL — YOU HAVE CONTROL") once Ctrl-A has taken the Human
        # lock (PWO-056; chord moved from `M` to Ctrl-A per
        # WO-P5-061-ENTRY); or `SPECTATE_LABEL` once `app.py`'s Ctrl-]
        # detach / broken-wire fallback has parked this client in
        # post-detach observation (PWO-055/PWO-057 -- observation chrome,
        # not a Mode). See `control_seat`'s own module docstring.
        # `attached=self.attached` below is this WO's own call-site fix:
        # PWO-056's interim `attached=not self.spectating` derivation is
        # replaced with the REAL per-instance state `app.py::_run_play` now
        # sets directly (attach success, Ctrl-] detach, Ctrl-A App-hold
        # release, and the broken-wire fallback all set `self.attached`
        # alongside `self.spectating`, never coupled through negation) --
        # honest state, not a derived proxy. `compose_control_strip_segments`
        # (WO-P5-060) replaced the retired flat-string strip join helper
        # call here so the mode-badge chip can carry its OWN reverse-video+
        # tone attr (`_control_strip_segment_attr`) distinct from the row's
        # plain liveness cluster -- drawn through `draw_segment_line`, the
        # segment-capable sibling of `draw_lines`/`draw_lines_attrs`. A
        # raising composer degrades to the pre-existing liveness-only
        # right-justified row (never crashes the draw pass), same
        # containment discipline as every other composer call in this
        # method. The A/R/T teach keys and run/record/panic cluster the
        # canon mock shows on this row still belong to the N5
        # mode-line-and-teach-controls WO -- not built here.
        control_strip = regions["control_strip"]
        control_strip_segments: list[tuple[str, int]] | None = None
        control_strip_fallback_lines: list[str] = []
        if control_strip is not None:
            cs_w = control_strip["w"]
            try:
                liveness_text = cockpit_liveness.compose_liveness_cluster(
                    status, now=now_val, width=cs_w, unicode_ok=uok
                )
            except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
                liveness_text = _CONTROL_STRIP_COMPOSE_FAILED
            # DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 1
            # ("one chip with Mode key -- merge APP+ARM, no separate APP +
            # ARM ON/OFF chips") retires the autopilot ARM chip's own
            # rendering on THIS row: `compose_control_strip_segments` below
            # is called with `trainer_labels=True`, which folds an armed
            # reading straight into the seat chip itself
            # (`^A)APP-ARMED`/`^A)MANUAL-HUMAN`) rather than a second
            # co-rendered chip beside it. `cockpit/arm.py` and
            # `compose_arm_chip` are UNCHANGED and still exist (this WO does
            # not touch that module) -- only this call site no longer reads
            # or renders their output. `arm_chip` is deliberately omitted
            # from the call below (defaults to `None`), the same additive
            # shape every other opt-out caller of this composer already
            # uses. This is a DELIBERATE relaxation of the daemon-verified
            # "no silent arm" guarantee those chips used to carry: the
            # merged label is aspirational client-side chrome for the
            # trainer ("App holding the seat" == "armed by default" under
            # this model), not a read of a real daemon arm state -- see
            # DECISION point 6 ("App-armed auto = default"). SPECTATE never
            # gets this treatment (`_trainer_seat_label` passes it through
            # unchanged), so a spectating instance can never claim ARMED.
            #
            # CONN also no longer renders on this row -- DECISION point 3
            # moved it to the row-1 profile strip (see that block above,
            # which already reads this SAME shared `status` snapshot and
            # `now_val`, not a second poll).
            #
            # WO-P5-072: the coverage meter — App-vs-Human live share.
            #
            # The counts are passed as `None` because THERE IS NO SOURCE FOR
            # THEM ON TIP, not as a placeholder someone should fill with a
            # plausible number. PWO-025 is PARTIAL: the control lock and
            # `VALID_SENDERS` are live, but `LedgerWriter` / the attach
            # keystroke ledger are still deferred in `session/daemon.py`, so
            # nothing in this tree records the per-send `actor` rows the
            # metric counts. `compose_coverage_meter` therefore renders
            # `COV ?` here on every draw, which is canon's required reading
            # ("Honest `?` when shares unknown — never invent",
            # `canon/engine/coverage-metrics.md`).
            #
            # When the ledger lands, ONLY this call changes — two counts
            # replace the two `None`s and the rest of the chain is already
            # correct. Deliberately NOT derived from `status`: the daemon's
            # status payload carries no coverage block, and synthesising one
            # from `last_sender` would report the most recent keystroke as
            # if it were a session-wide share.
            #
            # Passed as an explicit `(text, tone)` pair, not a bare string:
            # `control_seat._safe_arm_chip` 2-unpacks its argument, so a
            # plain string would be silently discarded (or, at exactly two
            # characters, split into text and tone) — a failure that would
            # look identical to "the meter didn't fit".
            try:
                meter_chip = (
                    cockpit_covermeter.compose_coverage_meter(
                        app=None, human=None, unicode_ok=uok
                    ),
                    cockpit_covermeter.METER_TONE,
                )
            except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
                meter_chip = None
            # WO-PLAY-STRIP-TRAINER-CHROME / DECISION point 4: `status_offer`
            # (WO-PLAY-OFFER-VISIBLE-ON-LIVE's mid-strip segment) is retired
            # here -- `status_line` now always routes into LOGS instead (see
            # that block above), never this row, so this composer call omits
            # `status_offer` entirely (defaults to `None`).
            try:
                raw_segments = cockpit_control_seat.compose_control_strip_segments(
                    spectating=self.spectating, attached=self.attached,
                    liveness_text=liveness_text, width=cs_w, unicode_ok=uok,
                    coverage_meter=meter_chip,
                    trainer_labels=True,
                    # WO-P5-066: the standing calm teach band. Composed
                    # unconditionally -- it is calm-state chrome that names
                    # the teach repertoire, not a state readout, so there is
                    # no status to gate it on. It self-drops when the row is
                    # too narrow (see `_compose_segments`).
                    # DECISION point 2 (WO-PLAY-STRIP-TRAINER-CHROME) retired
                    # the old A/R/T/V/U/H)old?/O)ffer?/Panic calm-band tokens
                    # in favor of `teachband.compose_teach_band`'s new
                    # E)xplore/P)ort Trade/C)argo/S)hip/│/T)rade Loop Chain/L)ist Loops/
                    # C)argo Hold Upgrade/S)hip Upgrade set -- the
                    # `port_trade_on`/`cargo_upgrade_on`/`ship_upgrade_on`
                    # toggles below read THIS instance's own local Play
                    # state (default-ON per DECISION point 2), not a
                    # daemon-reported fact; nothing in the App wires these
                    # keys yet (stubs, honest chrome only -- see
                    # `PlayShellScreen.__init__`'s own comment on these
                    # three attributes).
                    # WO-P5-069: while an Analyze overlay pass is open, the
                    # band slot shows the overlay badge instead of the calm
                    # affordance tokens. A live explore run still claims the
                    # hint slot via `explore_band` ahead of both (it is a
                    # live run; analyze is an overlay annotation).
                    teach_band=(
                        self.explore_band
                        if isinstance(self.explore_band, str) and self.explore_band
                        else (
                            cockpit_analyze.OVERLAY_LABEL
                            if self.analyze_session.is_open
                            else cockpit_teachband.compose_teach_band(
                                unicode_ok=uok,
                                port_trade_on=self.port_trade_on,
                                cargo_upgrade_on=self.cargo_upgrade_on,
                                ship_upgrade_on=self.ship_upgrade_on,
                            )
                        )
                    ),
                )
                control_strip_segments = [
                    (str(text), self._control_strip_segment_attr(tone))
                    for text, tone in raw_segments
                ]
            except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
                control_strip_segments = None
            if control_strip_segments is None:
                fallback_line = liveness_text.rjust(cs_w) if cs_w > 0 else ""
                control_strip_fallback_lines = [fallback_line] if cs_w > 0 else [""]
        if control_strip_segments is not None:
            cockpit_draw.draw_segment_line(
                self.stdscr, control_strip, control_strip_segments, boxed=False
            )
        else:
            cockpit_draw.draw_lines(
                self.stdscr, control_strip, control_strip_fallback_lines, curses.A_NORMAL, boxed=False
            )

        # WO-PLAY-AUTOLOOP-START: canon's ``L)chains`` library popup, drawn
        # over the centre region and BEFORE the confirm gate below -- the
        # confirm line must stay the last thing painted, since it is the one
        # prompt that spends.
        _cs_draw = getattr(self, "chains_session", None)
        if _cs_draw is not None and _cs_draw.is_open:
            try:
                _center = regions.get("center") or {}
                _w = _center.get("w")
                lines = cockpit_chains.compose_chain_lines(
                    _cs_draw,
                    unicode_ok=uok,
                    width=(_w - 4) if isinstance(_w, int) else 40,
                )
                cockpit_draw.draw_lines(
                    self.stdscr, regions.get("center"), lines, curses.A_NORMAL, boxed=True
                )
            except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
                # Same asymmetry the confirm gate states below: degrading
                # silently would leave an OPEN popup that `handle_key` still
                # routes Enter to as `chains_arm`, i.e. an invisible list
                # whose selection the operator cannot see. Closing it is the
                # only honest recovery.
                _cs_draw.close()

        # WO-PLAY-RULES-LIBRARY: blessed rules peek (read-only). Drawn like
        # chains over center; confirm/identity gates still paint last.
        _rl_draw = getattr(self, "rules_library_session", None)
        if _rl_draw is not None and _rl_draw.is_open:
            try:
                _center = regions.get("center") or {}
                _w = _center.get("w")
                lines = cockpit_rules_library.compose_rule_lines(
                    _rl_draw,
                    unicode_ok=uok,
                    width=(_w - 4) if isinstance(_w, int) else 40,
                )
                cockpit_draw.draw_lines(
                    self.stdscr, regions.get("center"), lines, curses.A_NORMAL, boxed=True
                )
            except Exception:  # noqa: BLE001
                _rl_draw.close()

        # WO-P5-063: the confirm-to-arm gate. Drawn LAST and over the control
        # strip's own row, so nothing can paint on top of the one prompt that
        # spends live turns. Canon puts it on the strip's row rather than in a
        # bordered modal ("a single confirm line",
        # `mode-line-and-teach-controls.md` "The confirm-gate dialog look").
        if self._arm_confirm is not None:
            try:
                line = cockpit_armconfirm.compose_arm_confirm_line(
                    self._arm_confirm[0], cycles=self._arm_confirm[1], unicode_ok=uok
                )
                cockpit_draw.draw_lines(
                    self.stdscr, control_strip, [line],
                    self._arm_confirm_attr(), boxed=False,
                )
            except Exception:  # noqa: BLE001 -- a raising composer must not crash the draw pass
                # Deliberate asymmetry with the strip's fallback above: that one
                # degrades to a quieter row, which is fine for telemetry. Here a
                # silent degrade would leave a PENDING ARM with no visible prompt
                # while `handle_key` still routes `y` to it -- an invisible live
                # gate. Cancelling is the only honest recovery.
                self._arm_confirm = None

        # WO-P5-070: draft approval gate — same row priority as arm confirm.
        if self._draft_approve is not None:
            try:
                screen = (self._draft_approve.get("when") or {}).get("screen", "?")
                line = cockpit_draft_approve.compose_draft_approve_line(screen, unicode_ok=uok)
                attr = self._control_strip_segment_attr(cockpit_draft_approve.DRAFT_APPROVE_TONE)
                cockpit_draw.draw_lines(
                    self.stdscr, control_strip, [line], attr, boxed=False,
                )
            except Exception:  # noqa: BLE001
                self._draft_approve = None

        # WO-PLAY-RULE-IDENTITY: typed entry outranks a stale approve prompt.
        if self._rule_identity is not None:
            try:
                line = cockpit_draft_approve.compose_identity_prompt(
                    self._rule_identity, unicode_ok=uok,
                )
                attr = self._control_strip_segment_attr(cockpit_draft_approve.IDENTITY_TONE)
                cockpit_draw.draw_lines(
                    self.stdscr, control_strip, [line], attr, boxed=False,
                )
            except Exception:  # noqa: BLE001
                self._rule_identity = None

        self.stdscr.refresh()

    def handle_key(self, key: int) -> str | None:
        """Return ``back`` / ``quit`` / ``attach`` / ``None``.

        ``"attach"`` (PWO-056, WO-P4-056) is a pure INTENT signal -- this
        class has no send-capable call or symbol of its own (``tests/
        test_spectate_no_send.py``'s guards). Ctrl-A (``MODE_KEY``, ASCII
        1, defined at module scope above -- the ONE place this keycode is
        assigned; `app.py` imports it from here rather than defining its
        own, so the two call sites can never silently drift onto
        different keycodes) is the Mode chord (ADR-002, Accepted
        2026-07-25, `canon/ADR/002-mode-chord-ctrl-a.md`; implemented
        here per WO-P5-061-ENTRY), superseding an earlier `M` draft
        specifically so bare `M` stays free as TradeWars' own Move
        command while attached: no single printable key may ever be
        Mode. This method is only ever reached for Ctrl-A while NOT
        attached (`app.py::_run_play` intercepts it itself, earlier,
        whenever it IS attached), so returning ``"attach"`` here
        unconditionally already covers BOTH legs of the toggle --
        Spectate->Human and App-hold->Human -- through the one existing
        attach call site; the Human->App-hold leg is `app.py`'s own new
        branch, not this method's. ``app.py::_run_play`` is what actually
        takes the daemon's Human control lock and flips
        ``self.spectating``/``self.attached``.
        """
        # WO-P5-063: the confirm-to-arm gate intercepts EVERYTHING while it is
        # up, and returns before any binding below can see the key. That
        # ordering is the contract, not a style choice: `Esc` below returns
        # `"back"` and `q` returns `"quit"`, so a gate placed lower down would
        # let a cancelling keystroke also tear down the screen -- "cancels with
        # no state change" (Accept #1) would be false for two of the four keys
        # the Accept names. Placing it first makes the capture total.
        #
        # Note there is no `y`-shaped hole below either: no binding in this
        # handler claims `y`, so the gate is the only thing that can ever act
        # on it. `resolve_arm_confirm_key` is default-deny (see its module),
        # so every key that is not `y`/`Y` -- named or not, including keycodes
        # this cockpit does not know yet -- lands on the cancel branch.
        if self._arm_confirm is not None:
            outcome = cockpit_armconfirm.resolve_arm_confirm_key(key)
            self._arm_confirm = None  # the gate is single-shot either way
            if outcome == cockpit_armconfirm.CONFIRM:
                # A pure INTENT signal, exactly like `"attach"` above it --
                # this class holds no arm-capable call. WO-P5-063 constraint:
                # "arm write-back is still read-only (062 stub); this WO only
                # adds the confirm gate, not the daemon call."
                return "arm_confirm"
            return None
        # WO-PLAY-RULE-IDENTITY: typed entry captures the strip while up
        # (same total-capture contract as arm confirm / draft approve).
        if self._rule_identity is not None:
            outcome = cockpit_draft_approve.resolve_identity_key(
                self._rule_identity, key,
            )
            if outcome == cockpit_draft_approve.COMPLETE:
                return "rule_identity"
            if outcome == cockpit_draft_approve.CANCEL:
                self._rule_identity = None
                return "rule_identity_cancel"
            # CONTINUE / REFUSE — stay in the session; REFUSE reason is on
            # the prompt via compose_identity_prompt.
            return None
        # WO-P5-070: draft approval gate — total capture while up (same ordering
        # contract as arm confirm above).
        if self._draft_approve is not None:
            outcome = cockpit_draft_approve.resolve_draft_approve_key(key)
            self._draft_approve = None
            if outcome == cockpit_draft_approve.CONFIRM:
                return "draft_approve"
            return "draft_reject"
        if key == 27:  # Esc
            # WO-PLAY-AUTOLOOP-START: the chains popup dismisses first, for
            # the same reason the Analyze overlay does -- Esc means "close
            # the thing that is up", and dropping the operator all the way
            # back to the launcher from an open money-path list would lose
            # their place for a keystroke they meant as "never mind".
            _cs = getattr(self, "chains_session", None)
            if _cs is not None and _cs.is_open:
                return "chains_close"
            # WO-PLAY-RULES-LIBRARY: same dismiss-first posture for the
            # read-only rules peek.
            _rl = getattr(self, "rules_library_session", None)
            if _rl is not None and _rl.is_open:
                return "rules_library_close"
            # WO-P5-069: if the Analyze overlay is open, Esc closes it
            # rather than returning to the launcher -- "A or Esc closes"
            # (WO-P5-069 Accept).  Only the overlay is dismissed; the
            # play shell stays up.
            # getattr guard: tests that use object.__new__ to skip __init__
            # may not have analyze_session set; treat its absence as closed.
            _as = getattr(self, "analyze_session", None)
            if _as is not None and _as.is_open:
                return "analyze_close"
            return "back"
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key == MODE_KEY:
            return "attach"
        # WO-PLAY-CONN-TOGGLE: arrow keys toggle focus to/from the CONN
        # chip in the control strip.  Any arrow direction cycles the single
        # focusable control (currently only CONN); future WOs that add more
        # focusable controls can extend this into a focus-ring.
        # WO-PLAY-AUTOLOOP-START: while the chains popup is up it owns the
        # cursor keys and Enter.  Placed ABOVE the CONN focus-ring so an
        # operator moving down a list of live-money actions cannot silently
        # be toggling a connection chip instead.
        _cs = getattr(self, "chains_session", None)
        if _cs is not None and _cs.is_open:
            if key in (curses.KEY_UP, ord("k")):
                return "chains_up"
            if key in (curses.KEY_DOWN, ord("j")):
                return "chains_down"
            if key in (curses.KEY_ENTER, 10, 13):
                # An INTENT to arm, never a start.  Canon: "selecting a chain
                # or launching a run *arms* a pending action and raises an
                # explicit confirm prompt ... A bare Enter must never fire a
                # launch" (`mode-line-and-teach-controls.md` §"Confirm-gate —
                # never one keystroke to live money").  app.py turns this into
                # `begin_arm_confirm`, and only a subsequent `y` spends.
                return "chains_arm"
        # WO-PLAY-RULES-LIBRARY: read-only peek owns cursor while open.
        # Enter is a no-op (peek, never arm).
        _rl = getattr(self, "rules_library_session", None)
        if _rl is not None and _rl.is_open:
            if key in (curses.KEY_UP, ord("k")):
                return "rules_library_up"
            if key in (curses.KEY_DOWN, ord("j")):
                return "rules_library_down"
            if key in (curses.KEY_ENTER, 10, 13):
                return None
        if key in (curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_UP, curses.KEY_DOWN):
            self._conn_focused = not self._conn_focused
            return None
        # Enter activates the currently-focused control (only CONN today).
        if key in (curses.KEY_ENTER, 10, 13):
            if self._conn_focused:
                return "conn_activate"
            return None
        # WO-PLAY-AUTOLOOP-START: canon's ``L)chains``.  Toggle, matching the
        # Analyze overlay's posture: a second press closes.  Both cases bind.
        # Returns a pure INTENT only -- this class has no send path
        # (``tests/test_spectate_no_send.py``'s guards remain intact).
        if key in (ord("l"), ord("L")):
            if _cs is not None and _cs.is_open:
                return "chains_close"
            return "chains_open"
        # WO-PLAY-RULES-LIBRARY: ``U)rules`` blessed-library peek (toggle).
        if cockpit_rules_library.resolve_rules_offer_key(key):
            if _rl is not None and _rl.is_open:
                return "rules_library_close"
            return cockpit_rules_library.RULES_OFFER_INTENT
        # WO-P5-069: A Analyze on-demand overlay.  Returns a pure INTENT
        # signal only -- this class has no send path of its own
        # (``tests/test_spectate_no_send.py``'s guards remain intact).
        # Both `a` and `A` bind, matching the A/R/T teach band's posture.
        # Second press while open returns "analyze_close" (toggle); first
        # press while closed returns "analyze_open".  Esc-while-open is
        # intercepted above.  This handler NEVER fires without an explicit
        # key press -- no auto-open on STOP alone.
        # getattr guard: same defence as the Esc branch above for
        # object.__new__-constructed instances that skip __init__.
        if key in (ord("a"), ord("A")):
            _as = getattr(self, "analyze_session", None)
            if _as is not None and _as.is_open:
                return "analyze_close"
            return "analyze_open"
        # WO-P5-068 RETIRED on calm path by WO-EXPLORE-TRADE-MODE-SPLIT:
        # teachband ``T)rade Loop Chain`` must mean Trade Loop execution of
        # the L-armed selection, not Assign-Trigger. Assign-Trigger remains
        # available via its own module / tests; calm ``T``/`t` is Trade Loop.
        if key in (ord("t"), ord("T")):
            return "trade_loop_toggle"
        # WO-P5-067: R Record scaffold.  Returns a pure INTENT signal only
        # ("record_toggle") -- this class has no send path of its own.
        # Both `r` and `R` bind, matching the A/R/T teach band's posture.
        # First press starts a recording; second press stops and saves.
        # `R` is NOT bound to attach/launch (WO constraint).
        if key in (ord("r"), ord("R")):
            return "record_toggle"        # WO-PLAY-REFLEX-ARM: V — preview what the taught rule library proposes
        # for the live screen. Returns a pure INTENT only; app.py calls
        # `reflex_propose` and (only on a fireable proposal) raises the
        # existing default-deny armconfirm gate. Never a send path.
        if cockpit_reflex_controls.resolve_reflex_offer_key(key):
            return cockpit_reflex_controls.REFLEX_OFFER_INTENT
        # WO-PLAY-STRIP-TRAINER-CHROME REVISE (hub 2026-07-31): P/C/S are
        # the trainer calm band's own local chrome toggles -- Port Trade,
        # Cargo Hold Upgrade, Ship Upgrade (`teachband.py`'s
        # `PORT_TRADE_LABEL`/`CARGO_UPGRADE_LABEL`/`SHIP_UPGRADE_LABEL`).
        # Each key flips ONLY this instance's own boolean and returns no
        # intent -- the same local-only shape the CONN focus-ring toggle
        # above already uses. WO-PLAY-STRIP-POLICY-AUTO wired the real
        # daemon-side spend gate these booleans drive (`app.py`'s
        # `_autonomy_auto_fire`, read on every App-armed idle tick from
        # OUTSIDE this class) -- this handler itself is unchanged by that
        # WO, it still only ever flips the boolean the gate later reads.
        #
        # `P` is DELIBERATELY no longer bound to `cockpit.panic` on this
        # calm path: the STATUS-DONE cut of this WO left the OLD `P panic`
        # wire live underneath the NEW `P)ort Trade` band label, a
        # plausible-but-wrong claim (the band advertised one meaning for
        # `P`, the handler still fired another) caught in hub REVISE.
        # `cockpit/panic.py` itself is UNCHANGED -- `resolve_panic_key`/
        # `PANIC_INTENT` still exist and its own module-level tests still
        # pin the bare function -- only THIS calm-path wire is retired.
        # Until a follow-on policy WO reintroduces a real halt control on
        # this surface, Esc (leave the play shell) and the Mode chord
        # (hand the seat back to the human) remain the operator's own
        # paths out of a run that needs stopping.
        #
        # Placed AFTER the A/R/T teach keys so it cannot shadow them.
        if key in (ord("p"), ord("P")):
            self.port_trade_on = not self.port_trade_on
            return None
        if key in (ord("c"), ord("C")):
            self.cargo_upgrade_on = not self.cargo_upgrade_on
            return None
        if key in (ord("s"), ord("S")):
            self.ship_upgrade_on = not self.ship_upgrade_on
            return None
        # WO-AUTOLOOP-RELAUNCH-COCKPIT: Space -- pause the taught run.
        #
        # Ungated, same reasoning `cockpit/panic.py` states for its own
        # (now calm-path-retired, see the P/C/S block above) halt key:
        # pausing STOPS further sends, it never spends any, so the
        # money-path confirm gate does not apply here either
        # (`cockpit/autoloop_controls.py` docstring). Placed after the
        # P/C/S toggles and the A/R/T teach keys above so it cannot shadow
        # any of them; no precondition on run state, same posture panic's
        # own module docstring gives: "a halt that refuses because the
        # cockpit believes nothing is running fails exactly when that
        # belief is wrong."
        if cockpit_autoloop_controls.resolve_pause_key(key):
            return cockpit_autoloop_controls.PAUSE_INTENT
        return None


class BankViewScreen:
    """Credential-bank rotation touchpoint — metadata only (WO-P1-015).

    ``error`` is the read-failure detail when the bank could not be read at all
    (``player_bank.BankUnreadable``), and it is mutually exclusive with
    ``entries``: an unreadable bank yielded no rows, so the screen renders the
    failure *instead of* the table -- header included. Painting the column
    header above nothing would imply a table with zero rows, which is the
    count this screen is not entitled to report
    (WO-AUDIT-PLAYER-BANK-STORE-HONESTY).
    """

    def __init__(
        self,
        stdscr: curses.window,
        entries: Sequence[dict[str, str]] | None = None,
        error: str | None = None,
    ) -> None:
        self.stdscr = stdscr
        self.entries = list(entries or ())
        self.error = error
        self._chrome = curses.A_NORMAL
        self._warn = curses.A_BOLD
        self._init_colors()

    def _init_colors(self) -> None:
        # Reuses _TonePalette (WO-P3-040 REVISE, Mack single-source MEDIUM +
        # CRITICAL pair-collision fix) instead of this screen's own former
        # curses.init_pair(1, ...)/init_pair(2, ...) calls -- "chrome"/"warn"
        # here mean exactly the tone table's "info"/"warn" tones (cyan
        # non-bold / yellow bold), and _TonePalette's own monochrome
        # fallback (bold "info", bold+underline "warn") is already
        # byte-identical to this class's prior standalone mono fallback, so
        # reusing it changes zero visible behavior while routing every pair
        # allocation through the one shared, collision-free mechanism.
        palette = _TonePalette()
        self._chrome = palette.attr("info")
        self._warn = palette.attr("warn")

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
        if self.error:
            # No header, no rows, no count -- the read failed, so the only
            # honest thing on screen is why, and that this is not emptiness.
            _safe_addstr(
                self.stdscr, y, 3, BANK_UNREADABLE_HEAD, self._warn | curses.A_BOLD
            )
            _safe_addstr(self.stdscr, y + 1, 5, self.error, self._warn)
            _safe_addstr(self.stdscr, y + 2, 3, BANK_UNREADABLE_HINT, curses.A_DIM)
            _safe_addstr(
                self.stdscr,
                max_y - 2,
                3,
                "Esc return to launcher",
                self._chrome,
            )
            self.stdscr.refresh()
            return

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
                BANK_EMPTY_LINE,
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


# Create-form cluster lives in create_form_screen.py (WO-SCREENS-CREATE-FORM-SPLIT).
# Lazy re-export: create_form_screen imports chrome helpers from this module, so an
# eager import here is a circular ImportError when create_form_screen loads first.
_CREATE_FORM_EXPORTS = (
    "CreateFormScreen",
    "_FORM_FIELDS",
    "_create_error_text",
    "validate_create_form",
)


def __getattr__(name: str):  # noqa: D401 — PEP 562 module attribute hook
    if name in _CREATE_FORM_EXPORTS:
        from tw2002_aiclient import create_form_screen as _cfs

        value = getattr(_cfs, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CREATE_FORM_EXPORTS))
